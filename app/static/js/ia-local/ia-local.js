let iaEngine = null,
  iaReady = false,
  iaModel = 'SmolLM2-1.7B-Instruct-q4f16_1-MLC';
let iaInicializacao = null;
let iaDiagnostico = { modo: 'pendente', motivo: '', modelo: null };

// SKIs — carregamento sob demanda (finance/campo/iot) + heatmap/chart no chat
const AMPLIA_SKIS = {
  recursos: {
    url: '/static/ia/skills/amplia-recursos.md',
    triggers: ['campo', 'recurso', 'registro', 'editar'],
    loaded: null,
  },
  finance: {
    url: '/static/ia/skills/amplia-finance.md',
    triggers: ['hedge', 'benchmark', 'lcdpr', 'seguro chuva', 'custo/ha'],
    loaded: null,
  },
  campo: {
    url: '/static/ia/skills/amplia-campo.md',
    triggers: ['VRA', 'NDVI', 'SPD', 'praga', 'guidance', 'as-applied'],
    loaded: null,
  },
  iot: {
    url: '/static/ia/skills/amplia-iot.md',
    triggers: ['CAN bus', 'BigBrother', 'mormaco', 'pivo', 'carbono', 'aerador'],
    loaded: null,
  },
};
async function loadAmpliaSKI(t) {
  const n = t.toLowerCase();
  for (const [k, s] of Object.entries(AMPLIA_SKIS)) {
    if (s.triggers.some((tr) => n.includes(tr.toLowerCase()))) {
      if (s.loaded) return s.loaded;
      try {
        const r = await fetch(s.url);
        s.loaded = r.ok ? await r.text() : '';
        return s.loaded;
      } catch (e) {
        return '';
      }
    }
  }
  return '';
}
function renderAmpliaChartInChat(container, widgetId, params) {
  // Busca /api/top-globais/<id> e injeta heatmap/chart no chat — VRA, CAN, hedge, benchmark, chuva, carbono
  fetch('/api/top-globais/' + widgetId + '/?' + new URLSearchParams(params), {
    credentials: 'same-origin',
  })
    .then((r) => r.json())
    .then((j) => {
      const d = j.data || j;
      let html = '';
      if (widgetId === 'kpi-vra-ndvi' && d.ndvi) {
        const heatmap =
          d.ndvi.heatmap_url || '/api/talhao/' + (d.ndvi.talhao_id || 1) + '/ndvi-heatmap/';
        html = `<div class="mt-2 p-2 bg-white dark:bg-slate-800 rounded-lg border"><div class="text-xs font-bold">VRA NDVI ${
          d.ndvi.ndvi_medio
        } — ${
          d.ndvi.sanidade
        }</div><img src="${heatmap}" class="w-full h-[120px] object-cover rounded mt-1" loading="lazy"/><div class="text-[10px] opacity-60">${
          d.acao || ''
        }</div></div>`;
      } else if (widgetId === 'kpi-can-bus' && d.chart) {
        const cid = 'chat-canbus-' + Date.now();
        html = `<div class="mt-2 p-2 bg-white dark:bg-slate-800 rounded-lg border"><div class="text-xs">CAN Bus ${
          d.rpm
        } RPM — ${d.dtc || 'OK'}</div><canvas id="${cid}" height="70"></canvas></div>`;
        setTimeout(() => {
          try {
            const c = document.getElementById(cid);
            if (c && window.Chart) {
              new Chart(c.getContext('2d'), {
                type: 'line',
                data: {
                  labels: d.chart.labels,
                  datasets: [
                    {
                      label: 'RPM',
                      data: d.chart.rpm,
                      borderColor: '#f59e0b',
                      tension: 0.4,
                      pointRadius: 0,
                    },
                    {
                      label: 'L/h',
                      data: d.chart.consumo,
                      borderColor: '#0f9d6e',
                      tension: 0.4,
                      pointRadius: 0,
                    },
                  ],
                },
                options: {
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: { legend: { display: false } },
                  scales: { x: { display: false }, y: { display: false } },
                },
              });
            }
          } catch (e) {}
        }, 100);
      } else if (widgetId === 'kpi-hedge-b3') {
        html = `<div class="mt-2 p-2 bg-white dark:bg-slate-800 rounded-lg border"><div class="text-xs font-bold">Hedge B3 ${
          d.recomendado
        } R$ (${d.sacas} sc @ ${
          d.strike
        })</div><div class="text-[10px] opacity-60">Chicago 80 → strike ${d.strike} — ${
          d.recomendado > 0 ? 'Travar ' + d.recomendado + ' sc' : 'Sem hedge'
        }</div><canvas id="chat-hedge-${Date.now()}" height="60"></canvas></div>`;
        setTimeout(() => {
          try {
            const c = document.querySelector('#chat-hedge-' + Date.now());
          } catch (e) {}
        }, 0);
      } else if (widgetId === 'kpi-benchmark-fbn') {
        const up = d.vs_media_pct > 0,
          col = up ? '#ef4444' : '#0f9d6e';
        html = `<div class="mt-2 p-2 bg-white dark:bg-slate-800 rounded-lg border"><div class="text-xs">Seu ${
          d.seu_custo_ha
        } vs média 2k ${d.media_2k}</div><div class="text-sm font-bold" style="color:${col}">${
          up ? '+' : ''
        }${
          d.vs_media_pct
        }%</div><div class="w-full bg-slate-200 rounded-full h-2 mt-1"><div class="h-2 rounded-full" style="width:${Math.min(
          100,
          50 + d.vs_media_pct / 2
        )}%;background:${col}"></div></div></div>`;
      } else if (widgetId === 'kpi-chuva-1km' || widgetId === 'kpi-seguro-chuva') {
        html = `<div class="mt-2 p-2 bg-white dark:bg-slate-800 rounded-lg border"><div class="text-xs">${
          d.mm_15min || d.chuva_60d
        }mm ${widgetId === 'kpi-chuva-1km' ? '15min' : '60d'} ${
          d.alerta || d.paga ? '⚠️ PAGA R$' + (d.valor || 5000) : 'OK'
        }</div></div>`;
      } else if (widgetId === 'kpi-carbono') {
        html = `<div class="mt-2 p-2 bg-white dark:bg-slate-800 rounded-lg border"><div class="text-xs font-bold">${d.tco2e} tCO2e</div><div class="text-[10px]">${d.area_ha}ha × ${d.tco2e_ha} Mombak +33% R$1bi</div></div>`;
      } else if (widgetId === 'kpi-lcdpr-sped') {
        html = `<div class="mt-2 p-2 bg-white dark:bg-slate-800 rounded-lg border"><div class="text-xs font-bold">${
          d.arquivo
        }</div><div class="text-[10px]">${d.sped ? '✓ SPED' : ''} ${
          d.auditavel ? 'Auditável' : ''
        } — ${
          d.ano
        }</div><div class="text-[9px] opacity-50">Baixar em /api/financeiro/lcdpr/download/?ano=${
          d.ano
        }</div></div>`;
      } else if (widgetId === 'kpi-as-applied') {
        const gapCol = d.gap_pct > 10 ? '#ef4444' : '#0f9d6e';
        html = `<div class="mt-2 p-2 bg-white dark:bg-slate-800 rounded-lg border"><div class="text-xs">Gap ${
          d.gap_pct
        }% — NDVI ${
          d.ndvi
        }</div><div class="w-full bg-slate-200 rounded-full h-2 mt-1"><div class="h-2 rounded-full" style="width:${Math.min(
          100,
          d.gap_pct * 3
        )}%;background:${gapCol}"></div></div><div class="text-[10px] opacity-60">${d.acao} ${
          d.gap_pct > 10 ? '→ Reaplicar VRA' : ''
        }</div></div>`;
      } else if (widgetId === 'kpi-praga-ai') {
        const col = d.praga === 'saudavel' ? '#0f9d6e' : '#ef4444';
        html = `<div class="mt-2 p-2 bg-white dark:bg-slate-800 rounded-lg border"><div class="text-xs font-bold" style="color:${col}">${
          d.praga
        } ${(d.confianca * 100).toFixed(0)}%</div><div class="text-[10px]">${d.acao} — foto ${
          d.foto_hash || 'demo'
        }</div></div>`;
      } else if (widgetId === 'kpi-rota-otimizada') {
        html = `<div class="mt-2 p-2 bg-white dark:bg-slate-800 rounded-lg border"><div class="text-xs">${
          d.km_total
        }km em ${d.tempo_h}h — 70 colheitadeiras</div><div class="text-[10px]">Economia ${
          d.economia_pct
        }% — ${(d.km_total * (d.economia_pct / 100)).toFixed(
          1
        )}km poupados</div><div class="w-full bg-slate-200 rounded-full h-2 mt-1"><div class="h-2 rounded-full bg-teal-500" style="width:${
          d.economia_pct * 6
        }%"></div></div></div>`;
      } else if (widgetId === 'kpi-guidance-ab') {
        html = `<div class="mt-2 p-2 bg-white dark:bg-slate-800 rounded-lg border"><div class="text-xs font-bold">${
          d.linha
        }</div><div class="text-[10px]">Precisão ${d.precisao_cm}cm — Auto-section ${
          d.auto_section ? 'ON' : 'OFF'
        }</div><div class="text-[9px] opacity-50">Talhao ${d.talhao_id}</div></div>`;
      } else if (widgetId === 'kpi-ai-cultura') {
        html = `<div class="mt-2 p-2 bg-white dark:bg-slate-800 rounded-lg border"><div class="text-sm font-bold">${
          d.cultura
        }</div><div class="text-xs">${(d.confianca * 100).toFixed(0)}% ${
          d.fonte
        }</div><div class="text-[9px] opacity-50">${d.lat},${d.lon}</div></div>`;
      } else if (widgetId === 'kpi-weigh-scale') {
        html = `<div class="mt-2 p-2 bg-white dark:bg-slate-800 rounded-lg border"><div class="text-lg font-bold">${d.sc_ha} sc/ha</div><div class="text-xs">NDVI ${d.ndvi} tempo real • Talhao ${d.talhao_id}</div></div>`;
      } else {
        html = `<div class="mt-2 p-2 bg-white dark:bg-slate-800 rounded text-xs"><pre class="whitespace-pre-wrap">${JSON.stringify(
          d,
          null,
          2
        ).slice(0, 400)}</pre></div>`;
      }
      if (container) container.insertAdjacentHTML('beforeend', html);
    })
    .catch(() => {});
}

const RECURSOS_API = {
  culturas: '/api/culturas/',
  propriedades: '/api/propriedades/',
  talhoes: '/api/talhoes/',
  safras: '/api/safras/',
  insumos: '/api/insumos/',
  'aplicacoes-insumo': '/api/aplicacoes-insumo/',
  funcionarios: '/api/funcionarios/',
  operarios: '/api/operarios/',
  maquinarios: '/api/maquinarios/',
  lancamentos: '/api/lancamentos/',
  animais: '/api/animais/',
  'producao-animal': '/api/producao-animal/',
  // `animais-individuais`, `leituras`, `pesagens`, `eventos-sanitarios` e
  // `gateways` vivem uma unica vez, no bloco "CORRECOES_MINUCIAS" mais abaixo
  // — que e' onde esta a anotacao do modelo (`PE.AnimalIndividual`, etc.).
  //
  // Estavam AQUI E ALI, com o mesmo valor. Num object literal o ultimo ganha
  // e o primeiro e' descartado EM SILENCIO: nao ha erro, nao ha aviso, e o
  // comentario de cada um jurava que o valor de la era o que valia. O
  // efeito pratico e' o pior dos silencios — editar a linha daqui nao fazia
  // nada, e nada dizia que nao tinha feito.
  //
  // MEDIDO 2026-10-04 (agente 4): `no-dupe-keys` no `npm run lint`. O lint
  // so passou a apanhar isto depois de deixar de demorar 240 s e de
  // percorrer `.venv/` e `staticfiles/` — ver `eslint.config.mjs`.
  estoque: '/api/estoque/',
  colmeias: '/api/colmeias/',
  'producao-apiario': '/api/producao-apiario/',
  operacoes: '/api/operacoes/',
  'centros-custo': '/api/centros-custo/',
  'lancamentos-detalhados': '/api/lancamentos-detalhados/',
  'contas-bancarias': '/api/contas-bancarias/',
  'movimentacoes-bancarias': '/api/movimentacoes-bancarias/',
  estacoes: '/api/estacoes-meteo/',
  // `sensores` estava AUSENTE. O ramo (c) da pergunta de fonte de clima
  // fazia `RECURSOS_API['sensores'] || '/api/sensores/'` — o `||` salvava a
  // chamada, mas o nome ficava fora do dicionário que TODOS os outros
  // caminhos usam. Um nome ausente não falha: ele faz o próximo que o
  // procurar pelo mapa trabalhar com um literal, e o literal envelhece
  // sozinho. Por isso fica escrito aqui, ao lado dos outros.
  sensores: '/api/sensores/',
  prescricoes: '/api/prescricoes-vra/',
  zarc: '/api/zarc/',
  receituarios: '/api/receituarios/',
  comandos: '/api/iot/comandos/',
  devices: '/api/iot/devices/',
  commodities: '/api/commodities/',
  cotacoes: '/api/financeiro/cotacoes/',
  clima: '/api/previsao-clima/',
  // CORREÇÕES MINUCIAS — todos os gargalos encontrados (CORRECOES_MINUCIAS.md)
  'animais-individuais': '/api/animais-individuais/', // PE.AnimalIndividual (14 campos)
  pesagens: '/api/pesagens/', // PE.Pesagem (data, peso, tipo)
  piquetes: '/api/piquetes/', // PE.Piquete (nome, area, status, animais)
  'protocolos-sanitarios': '/api/protocolos-sanitarios/', // PE.ProtocoloSanitario
  'eventos-sanitarios': '/api/eventos-sanitarios/', // PE.EventoSanitario (tipo, produto, proxima_dose)
  telemetria: '/api/telemetria/', // IOT.TelemetryData (metric, value, timestamp, qualidade)
  'estacoes-meteo': '/api/estacoes-meteo/', // IOT.EstacaoMeteo (nome, lat, lon, ativa)
  leituras: '/api/leituras-sensor/', // IOT.LeituraSensor (tipo, valor, unidade)
  'regras-alerta': '/api/regras-alerta/', // IOT.RegraAlertaTelemetria (metric, tipo, severidade)
  'alertas-telemetria': '/api/alertas-telemetria/', // IOT.AlertaTelemetria (mensagem, resolvido, timestamp)
  gateways: '/api/iot/gateways/', // IOT.Gateway (nome, tipo, status, ultimo_contato)
  'custo-producao': '/api/custo-producao/', // CUSTOS.CustoProducao (insumos, maquina, mao_de_obra, custo_total, lucro, margem)
  'movimentacoes-estoque': '/api/movimentacoes-estoque/', // EST.MovimentacaoEstoque (tipo, quantidade, nf, data, responsavel)
  'fila-controle': '/api/fila-controle/', // EST.FilaControle (codigo, peso_inicial, peso_saldo, conferido)
  'pesagens-entrega': '/api/pesagens-entrega/', // EST.PesagemEntrega (peso_devolvido, divergencia)
  'ordens-compra': '/api/ordens-compra/', // EST.OrdemCompra (status, fornecedor, valor_total, data_entrega)
  inventarios: '/api/inventarios/', // EST.Inventario
  'inventario-itens': '/api/inventario-itens/', // EST.InventarioItem
  rastreabilidade: '/api/rastreabilidade/', // RASTREABILIDADE.RastreabilidadeSafra
  'rastro-itens': '/api/rastro-itens/', // RASTREABILIDADE.RastroItem
  relatorios: '/api/relatorios/', // RELATORIO.RelatorioGerado
  'relatorio-templates': '/api/relatorio-templates/', // RELATORIO.RelatorioTemplate
  'planos-safra': '/api/planos-safra/', // SAFRA.PlanoSafra
};

const PAGINAS = {
  dashboard: '/',
  safras: '/cadastro/safra/',
  talhoes: '/cadastro/talhao/',
  culturas: '/cadastro/cultura/',
  insumos: '/cadastro/insumo/',
  maquinarios: '/cadastro/maquinario/',
  funcionarios: '/cadastro/funcionario/',
  propriedades: '/cadastro/propriedade/',
  financeiro: '/cadastro/financeiro/',
  estoque: '/cadastro/estoque/',
  estoque_geral: '/estoque/geral/',
  agenda: '/equipe/agenda/',
  agenda_agricola: '/agenda/agricola/',
  agenda_pecuaria: '/agenda/pecuaria/',
  sensores: '/iot/sensores/',
  dispositivos: '/iot/dispositivos/',
  comandos: '/iot/comandos/',
  perfil: '/perfil/config/',
};

// Wizard de cadastro - checklist por recurso (perguntas sequenciais, como listinha de tarefas)
const ESQUEMAS_CADASTRO = {
  funcionarios: [
    {
      campo: 'nome',
      pergunta: 'Qual o nome completo do funcionário?',
      tipo: 'text',
      obrigatorio: true,
      placeholder: 'Ex: João da Silva',
    },
    {
      campo: 'cargo',
      pergunta: 'Qual o cargo?',
      tipo: 'select',
      opcoes: [
        'TRATORISTA',
        'OPERADOR_PULVERIZADOR',
        'VAQUEIRO',
        'GERENTE',
        'AUX_CAMPO',
        'MOTORISTA',
        'MECANICO_AGRICOLA',
        'OUTRO',
      ],
      obrigatorio: true,
    },
    {
      campo: 'salario',
      pergunta: 'Salário (R$)?',
      tipo: 'number',
      obrigatorio: true,
      placeholder: '3500',
    },
    {
      campo: 'telefone',
      pergunta: 'Telefone/WhatsApp?',
      tipo: 'text',
      obrigatorio: false,
      placeholder: '(66) 99999-0000',
    },
    {
      campo: 'data_admissao',
      pergunta: 'Data de admissão?',
      tipo: 'date',
      obrigatorio: true,
      valorPadrao: () => new Date().toISOString().slice(0, 10),
    },
  ],
  safras: [
    {
      campo: 'nome',
      pergunta: 'Nome da safra?',
      tipo: 'text',
      obrigatorio: true,
      placeholder: 'Safra 24/25 Soja',
    },
    {
      campo: 'ano',
      pergunta: 'Ano da safra?',
      tipo: 'number',
      obrigatorio: true,
      valorPadrao: () => new Date().getFullYear(),
    },
    {
      campo: 'cultura',
      pergunta: 'Cultura (ex: 28077=Soja, 28079=Milho)?',
      tipo: 'text',
      obrigatorio: false,
    },
    { campo: 'area', pergunta: 'Área em hectares?', tipo: 'number', obrigatorio: false },
  ],
  talhoes: [
    {
      campo: 'nome',
      pergunta: 'Nome do talhão?',
      tipo: 'text',
      obrigatorio: true,
      placeholder: 'Talhão 03',
    },
    { campo: 'area', pergunta: 'Área (ha)?', tipo: 'number', obrigatorio: true },
    { campo: 'cultura', pergunta: 'Cultura atual?', tipo: 'text', obrigatorio: false },
  ],
  operacoes: [
    {
      campo: 'titulo',
      pergunta: 'Qual a tarefa? (ex: Pulverizar soja)',
      tipo: 'text',
      obrigatorio: true,
    },
    {
      campo: 'tipo',
      pergunta: 'Tipo? AGRICOLA, PECUARIA ou GERAL',
      tipo: 'select',
      opcoes: ['AGRICOLA', 'PECUARIA', 'GERAL'],
      obrigatorio: true,
      valorPadrao: () => 'AGRICOLA',
    },
    {
      campo: 'talhao',
      pergunta: 'Qual talhão? (nome ou ID, ou "pular")',
      tipo: 'text',
      obrigatorio: false,
    },
    {
      campo: 'funcionario',
      pergunta: 'Qual funcionário? (nome ou ID, ou "pular")',
      tipo: 'text',
      obrigatorio: false,
    },
    {
      campo: 'data_agendada',
      pergunta: 'Data para executar?',
      tipo: 'date',
      obrigatorio: true,
      valorPadrao: () => new Date().toISOString().slice(0, 10),
    },
  ],
  estoque: [
    {
      campo: 'nome',
      pergunta: 'Nome do item?',
      tipo: 'text',
      obrigatorio: true,
      placeholder: 'Ex: Óleo 15W40',
    },
    { campo: 'quantidade', pergunta: 'Quantidade?', tipo: 'number', obrigatorio: true },
    {
      campo: 'unidade',
      pergunta: 'Unidade? (un, L, kg, sc)',
      tipo: 'text',
      obrigatorio: true,
      valorPadrao: () => 'un',
    },
    {
      campo: 'local',
      pergunta: 'Local no estoque?',
      tipo: 'text',
      obrigatorio: false,
      placeholder: 'Oficina',
    },
  ],
  insumos: [
    {
      campo: 'nome',
      pergunta: 'Nome do insumo?',
      tipo: 'text',
      obrigatorio: true,
      placeholder: 'Ex: Ureia',
    },
    {
      campo: 'categoria',
      pergunta: 'Categoria? (FERTILIZANTE, DEFENSIVO, SEMENTE)',
      tipo: 'text',
      obrigatorio: true,
    },
    { campo: 'quantidade', pergunta: 'Quantidade?', tipo: 'number', obrigatorio: false },
    {
      campo: 'unidade',
      pergunta: 'Unidade?',
      tipo: 'text',
      obrigatorio: false,
      valorPadrao: () => 'kg',
    },
  ],
  culturas: [
    {
      campo: 'nome',
      pergunta: 'Nome da cultura?',
      tipo: 'text',
      obrigatorio: true,
      placeholder: 'Ex: Soja',
    },
    { campo: 'ciclo_dias', pergunta: 'Ciclo em dias?', tipo: 'number', obrigatorio: false },
  ],
  estacoes: [
    {
      campo: 'nome',
      pergunta: 'Nome da estação meteorológica?',
      tipo: 'text',
      obrigatorio: true,
      placeholder: 'Ex: Estação Fazenda Norte',
    },
    /* `latitude` e `longitude` são OBRIGATÓRIAS no modelo (`EstacaoMeteo`,
     * `DecimalField` sem `null`/`blank`), portanto obrigatórias aqui.
     *
     * Estavam marcadas `obrigatorio: false` e havia um quarto campo,
     * `municipio`, que `EstacaoMeteo` NÃO tem. O efeito era um cadastro que
     * ia collecting dados e acabava num `400 {"latitude": ["Este campo é
     * obrigatório."]}` — com a conversa inteira já feita.
     *
     * `municipio` saiu porque o servidor o deita fora: não é campo do
     * serializer. Pedir um dado que ninguém guarda é pior que não pedir.
     */
    {
      campo: 'latitude',
      pergunta: 'Latitude da estação? (Ex: -21.55)',
      tipo: 'number',
      obrigatorio: true,
      placeholder: 'Ex: -21.55',
    },
    {
      campo: 'longitude',
      pergunta: 'Longitude da estação? (Ex: -46.37)',
      tipo: 'number',
      obrigatorio: true,
      placeholder: 'Ex: -46.37',
    },
  ],
  propriedades: [
    {
      campo: 'nome',
      pergunta: 'Nome da propriedade/fazenda?',
      tipo: 'text',
      obrigatorio: true,
      placeholder: 'Ex: Fazenda Santa Luzia',
    },
    {
      campo: 'area_total',
      pergunta: 'Área total em hectares?',
      tipo: 'number',
      obrigatorio: false,
    },
    {
      campo: 'municipio',
      pergunta: 'Município?',
      tipo: 'text',
      obrigatorio: false,
      placeholder: 'Ex: Alterosa - MG',
    },
  ],
};
let iaCadastroPendente = null;

// ══════════════════════════════════════════════════════════════
// FORMATAÇÃO NATURAL — converte dados da API em texto humano
// ══════════════════════════════════════════════════════════════
function fmtMoeda(v) {
  if (v == null || isNaN(v)) return 'R$ —';
  return Number(v).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}
function fmtNum(v, dec = 2) {
  if (v == null || isNaN(v)) return '—';
  return Number(v).toLocaleString('pt-BR', {
    minimumFractionDigits: 0,
    maximumFractionDigits: dec,
  });
}

function formatarDadosNatural(recurso, data) {
  const items = data?.results || (Array.isArray(data) ? data : null);
  const count = data?.count ?? items?.length ?? 0;

  // ── Propriedade / Cidade / Localização (correção: não inventar cidade) ──
  if (
    recurso === 'propriedades' ||
    recurso === 'propriedade' ||
    recurso === 'local' ||
    recurso === 'cidade'
  ) {
    const prop = data?.results?.[0] || data || {};
    if (!prop || !prop.nome)
      return 'Não encontrei propriedade cadastrada. Quer cadastrar via /cadastro/propriedade/?';
    const partes = [`🏡 ${prop.nome}`];
    if (prop.cidade) partes.push(`cidade: ${prop.cidade}`);
    if (prop.uf) partes.push(`UF: ${prop.uf}`);
    if (prop.bioma) partes.push(`bioma: ${prop.bioma}`);
    if (prop.area_total) partes.push(`área: ${fmtNum(prop.area_total)} ha`);
    return `📍 Sua fazenda: ${partes.join(' | ')}.`;
  }

  // ── Perfil / Tema / Configuração (correção: não inventar tema) ──
  if (
    recurso === 'perfil' ||
    recurso === 'perfil-usuario' ||
    recurso === 'tema' ||
    recurso === 'config'
  ) {
    const perfil = data?.results?.[0] || data || {};
    if (!perfil || (!perfil.tema && !perfil.tipo_usuario))
      return 'Não encontrei perfil configurado. Verifique /perfil/config/.';
    const partes = [`👤 ${perfil.tipo_usuario || 'Produtor'}`];
    if (perfil.tema) partes.push(`tema: ${perfil.tema}`);
    if (perfil.idioma) partes.push(`idioma: ${perfil.idioma}`);
    if (perfil.area_servidor) partes.push(`área: ${perfil.area_servidor}`);
    return `⚙️ Configuração do perfil: ${partes.join(' | ')}.`;
  }

  // ── Agregação / Comparação — maior quantidade / soma / média (correção: consultar DB, não inventar) ──
  if (
    recurso === 'agregacao' ||
    recurso === 'maior' ||
    recurso === 'comparativo' ||
    recurso === 'resumo'
  ) {
    // Se os dados vêm do backend (aggregate real), formata; se vazio, pergunta
    if (!items || items.length === 0) {
      if (data && data.total) return `📊 Agregação: total de ${fmtNum(data.total)} registros.`;
      return 'Preciso confirmar o recurso para fazer a agregação real (não invento números). Qual cultura / safra / talhão / animal você quer comparar?';
    }
    const nomes = items.slice(0, 5).map((i) => i.nome || i.titulo || i.cultura || '—');
    return `📊 ${count} registros encontrados para comparação: ${nomes.join(
      ', '
    )}. (Dados reais do banco — sem invento)`;
  }

  // ── Clima ──
  if (recurso === 'clima' || recurso === 'previsao-clima') {
    // A FORMA real desta resposta é `{cidade, fonte, atual, previsao}` — as
    // três fontes (INMET, OpenWeatherMap e o fallback) devolvem exactamente
    // isto. O código anterior procurava `temperatura_max`, `precipitacao`,
    // `chuva`… campos que não existem em lado nenhum dela, e `previsao` é uma
    // LISTA: `p.temperatura_max` dava undefined, `partes` ficava vazio, e o
    // productor lia um despejo de JSON cru em vez duma frase.
    //
    // O que era pior que o formato: o `fonte: "simulado"` do fallback nunca
    // era lido. O servidor dizia "isto não foi medido" e o chat descartava a
    // palavra. Medido antes da correcção, com o payload real do servidor:
    //
    //     Previsao do clima: [dia: Hoje, temp: 28, umidade: 65,
    //                         descricao: Ensolarado, ...]
    //
    // 28 °C que ninguém mediu, com a forma de uma previsão. Um número
    // inventado que passa por medido é pior do que um 500: o 500 avisa.
    const fonte = String(data?.fonte || '').toLowerCase();
    const simulado = fonte === 'simulado' || fonte === 'fallback';

    // Sem fonte medida, não há previsão. Dizê-lo é a resposta honesta, e é
    // também a mais útil: o produtor sabe o que precisa de configurar.
    if (simulado) {
      const onde = data?.cidade ? ` para ${data.cidade}` : '';
      return (
        `Não tenho previsão do tempo${onde}: a fonte meteorológica não ` +
        `respondeu e não vou inventar um número. Configure a estação em ` +
        `Estações Meteorológicas, ou o INMET liga sozinho quando há rede.`
      );
    }

    // `atual` é o dia de hoje; `previsao` são os dias seguintes.
    const dias = Array.isArray(data?.previsao) ? data.previsao : data?.atual ? [data.atual] : [];
    const hoje = data?.atual || dias[0];
    if (!hoje || (typeof hoje === 'object' && Object.keys(hoje).length === 0))
      return 'Não encontrei dados de previsão no momento. Verifique se a estação meteorológica está configurada.';

    // `null` é "a fonte não disse", e é distinto de 0: uma humidade de 0 % é
    // um número impossível, e mostrá-lo como medido seria inventar outro.
    const num = (v) => (v === null || v === undefined ? null : Number(v));
    const temp = num(hoje.temp ?? hoje.temperatura);
    const umid = num(hoje.umidade ?? hoje.umidade_max);
    const desc = hoje.descricao || hoje.condicao || hoje.resumo;

    if (temp === null && umid === null && !desc)
      return 'A fonte respondeu, mas sem temperatura nem humidade. Não tenho previsão que sirva para decidir.';

    const partes = [];
    if (temp !== null && Number.isFinite(temp)) partes.push(`${Math.round(temp)}°C`);
    if (umid !== null && Number.isFinite(umid)) partes.push(`umidade ${Math.round(umid)}%`);
    if (desc) partes.push(String(desc));
    if (partes.length === 0)
      return 'A fonte respondeu, mas não tenho o que mostrar. Não tenho previsão que sirva para decidir.';

    const origem = fonte ? ` (fonte: ${fonte})` : '';
    const resto = dias.length > 1 ? ` Próximos dias: ${dias.length - 1}.` : '';
    return `🌤️ Previsão para hoje${origem}: ${partes.join(', ')}.${resto}`;
  }

  // ── Commodities/Cotações ──
  if (recurso === 'commodities' || recurso === 'cotacoes') {
    const lista = items || (data ? [data] : []);
    if (lista.length === 0) return 'Não encontrei cotações no momento.';
    const linhas = lista.slice(0, 5).map((c) => {
      const nome = c.cultura || c.produto || c.nome || c.commodity || '—';
      const preco = c.preco || c.valor || c.cotacao || c.preco_saca;
      return `• ${nome}: ${preco ? fmtMoeda(preco) : '—'}${c.unidade ? '/' + c.unidade : '/sc'}${
        c.data ? ' (' + c.data + ')' : ''
      }`;
    });
    return `📊 Cotações atuais:\n${linhas.join('\n')}`;
  }

  // ── Financeiro / Fluxo de Caixa ──
  if (recurso === 'lancamentos' || recurso === 'financeiro' || recurso === 'cashflow') {
    if (data?.fluxo_caixa != null || data?.saldo != null || data?.total != null) {
      const partes = [];
      if (data.fluxo_caixa != null) partes.push(`Fluxo de caixa: ${fmtMoeda(data.fluxo_caixa)}`);
      if (data.saldo != null) partes.push(`Saldo: ${fmtMoeda(data.saldo)}`);
      if (data.total_receitas != null) partes.push(`Receitas: ${fmtMoeda(data.total_receitas)}`);
      if (data.total_despesas != null) partes.push(`Despesas: ${fmtMoeda(data.total_despesas)}`);
      if (data.total != null && partes.length === 0) partes.push(`Total: ${fmtMoeda(data.total)}`);
      if (data.lucro != null) partes.push(`Lucro: ${fmtMoeda(data.lucro)}`);
      return `💰 ${partes.join(' | ')}`;
    }
    if (items && items.length > 0) {
      const resumo = items.slice(0, 5).map((l) => {
        const desc = l.descricao || l.titulo || l.categoria || '—';
        const val = l.valor || l.total;
        return `• ${desc}: ${fmtMoeda(val)}`;
      });
      return `💰 ${count} lançamentos encontrados. Últimos:\n${resumo.join('\n')}`;
    }
    return 'Não encontrei dados financeiros registrados.';
  }

  // ── Safras / Produção ──
  if (recurso === 'safras') {
    if (!items || items.length === 0) return 'Nenhuma safra encontrada no sistema.';
    const linhas = items.slice(0, 5).map((s) => {
      const nome = s.nome || `Safra ${s.ano || ''}`;
      const partes = [nome];
      if (s.cultura_nome || s.cultura) partes.push(s.cultura_nome || s.cultura);
      if (s.area) partes.push(`${fmtNum(s.area)}ha`);
      if (s.producao_total != null) partes.push(`produção: ${fmtNum(s.producao_total)} ton`);
      if (s.produtividade != null) partes.push(`${fmtNum(s.produtividade)} sc/ha`);
      if (s.status) partes.push(s.status.toLowerCase());
      return `• ${partes.join(' — ')}`;
    });
    return `🌱 ${count} safra(s) encontrada(s):\n${linhas.join('\n')}`;
  }

  // ── Dashboard ──
  if (recurso === 'dashboard') {
    const partes = [];
    if (data?.producao_total != null)
      partes.push(`Produção total: ${fmtNum(data.producao_total)} ton`);
    if (data?.area_total != null) partes.push(`Área total: ${fmtNum(data.area_total)}ha`);
    if (data?.receita_total != null) partes.push(`Receita: ${fmtMoeda(data.receita_total)}`);
    if (data?.despesa_total != null) partes.push(`Despesas: ${fmtMoeda(data.despesa_total)}`);
    if (data?.lucro != null) partes.push(`Lucro: ${fmtMoeda(data.lucro)}`);
    if (data?.safras_ativas != null) partes.push(`${data.safras_ativas} safra(s) ativa(s)`);
    if (data?.alertas != null) partes.push(`${data.alertas} alerta(s)`);
    if (partes.length === 0) {
      // tenta extrair qualquer campo numérico relevante
      for (const [k, v] of Object.entries(data || {})) {
        if (typeof v === 'number' && !k.startsWith('_'))
          partes.push(`${k.replace(/_/g, ' ')}: ${fmtNum(v)}`);
        if (partes.length >= 6) break;
      }
    }
    if (partes.length === 0) return 'Dashboard carregado, mas sem dados resumidos disponíveis.';
    return `📋 Resumo do dashboard:\n${partes.map((p) => `• ${p}`).join('\n')}`;
  }

  // ── Culturas ──
  if (recurso === 'culturas') {
    if (!items || items.length === 0) return 'Nenhuma cultura cadastrada no sistema.';
    const nomes = items.map((c) => c.nome || c.cultura || '—');
    return `🌿 ${count} cultura(s) cadastrada(s): ${nomes.join(', ')}.`;
  }

  // ── Talhões ──
  if (recurso === 'talhoes') {
    if (!items || items.length === 0) return 'Nenhum talhão cadastrado.';
    const linhas = items.slice(0, 8).map((t) => {
      const partes = [t.nome || '—'];
      if (t.area) partes.push(`${fmtNum(t.area)}ha`);
      if (t.cultura_nome || t.cultura) partes.push(t.cultura_nome || t.cultura);
      return `• ${partes.join(' — ')}`;
    });
    return `🗺️ ${count} talhão(ões):\n${linhas.join('\n')}`;
  }

  // ── Funcionários ──
  if (recurso === 'funcionarios') {
    if (!items || items.length === 0) return 'Nenhum funcionário cadastrado.';
    const linhas = items
      .slice(0, 6)
      .map((f) => `• ${f.nome || '—'} — ${(f.cargo || '—').toLowerCase().replace(/_/g, ' ')}`);
    return `👥 ${count} funcionário(s):\n${linhas.join('\n')}`;
  }

  // ── Estoque ──
  if (recurso === 'estoque') {
    if (!items || items.length === 0) return 'Estoque vazio ou sem itens cadastrados.';
    const linhas = items
      .slice(0, 6)
      .map((i) => `• ${i.nome || '—'}: ${fmtNum(i.quantidade || 0)} ${i.unidade || 'un'}`);
    return `📦 ${count} item(ns) no estoque:\n${linhas.join('\n')}`;
  }

  // ── Operações ──
  if (recurso === 'operacoes') {
    if (!items || items.length === 0) return 'Nenhuma operação/tarefa encontrada.';
    const linhas = items.slice(0, 5).map((o) => {
      const status = o.status ? ` [${o.status.toLowerCase()}]` : '';
      return `• ${o.titulo || o.descricao || '—'}${status}${
        o.data_agendada ? ' — ' + o.data_agendada : ''
      }`;
    });
    return `📋 ${count} operação(ões):\n${linhas.join('\n')}`;
  }

  // ── Insumos ──
  if (recurso === 'insumos') {
    if (!items || items.length === 0) return 'Nenhum insumo cadastrado.';
    const linhas = items
      .slice(0, 6)
      .map((i) => `• ${i.nome || '—'} (${(i.categoria || '—').toLowerCase()})`);
    return `🧪 ${count} insumo(s):\n${linhas.join('\n')}`;
  }

  // ── Maquinários ──
  if (recurso === 'maquinarios') {
    if (!items || items.length === 0) return 'Nenhum maquinário cadastrado.';
    const linhas = items
      .slice(0, 5)
      .map((m) => `• ${m.nome || m.modelo || '—'}${m.tipo ? ' (' + m.tipo + ')' : ''}`);
    return `🚜 ${count} maquinário(s):\n${linhas.join('\n')}`;
  }

  // ── Propriedades ──
  if (recurso === 'propriedades') {
    if (!items || items.length === 0) return 'Nenhuma propriedade cadastrada.';
    const linhas = items.map((p) => {
      const partes = [p.nome || '—'];
      if (p.area_total) partes.push(`${fmtNum(p.area_total)}ha`);
      if (p.cidade || p.municipio) partes.push(p.cidade || p.municipio);
      return `• ${partes.join(' — ')}`;
    });
    return `🏡 ${count} propriedade(s):\n${linhas.join('\n')}`;
  }

  // ── Animais ──
  if (recurso === 'animais') {
    if (!items || items.length === 0) return 'Nenhum animal cadastrado.';
    return `🐄 ${count} animal(is) cadastrado(s).`;
  }

  // ── Eventos sanitários ──
  if (recurso === 'eventos-sanitarios') {
    if (!items || items.length === 0) return 'Nenhum evento sanitário registrado.';
    const linhas = items
      .slice(0, 5)
      .map((e) => `• ${e.tipo || e.descricao || '—'} — ${e.data || ''}`);
    return `💉 ${count} evento(s) sanitário(s):\n${linhas.join('\n')}`;
  }

  // ── Sensores ──
  //
  // `/api/sensores/` devolve `{sensores: [{nome, propriedade, ativa…}], total}`.
  // O ramo antigo só varria números de topo, e `total` é o único — a
  // resposta era "📡 Sensores: total: 2". O produtor perguntou QUE sensores,
  // recebeu uma contagem, e não soube o nome de nenhum. A pergunta foi
  // respondida com o número dela.
  //
  // `total: 0` aqui é um zero CONTADO — `sensores_data` consulta a base —,
  // por isso pode ser dito como é. O que não pode é dizer "não há sensores"
  // quando o `total` não veio.
  if (recurso === 'sensores') {
    const lista = Array.isArray(data?.sensores)
      ? data.sensores
      : Array.isArray(data)
        ? data
        : items;
    if (lista && lista.length > 0) {
      const linhas = lista.slice(0, 8).map((s) => {
        const partes = [s.nome || '—'];
        if (s.propriedade) partes.push(s.propriedade);
        // `ativa === false` é um facto que muda a leitura de "2 sensores":
        // uma estação desligada não mede. Distinguir `false` de `undefined`
        // é o que evita escrever "(inativa)" em tudo.
        if (s.ativa === false) partes.push('(inativa)');
        return `• ${partes.join(' — ')}`;
      });
      const resto =
        lista.length > linhas.length ? `\n…e mais ${lista.length - linhas.length}.` : '';
      return `📡 ${lista.length} sensor(es):\n${linhas.join('\n')}${resto}`;
    }
    if (typeof data?.total === 'number') {
      // Zero contado. Diz-se o zero E a saída, porque "0 sensores" sem saída
      // é um beco — e (c) é pedido logo depois de alguém ouvir que não tem
      // estação. Um beco aqui empurra a pessoa a desistir do clima.
      return '📡 Não tem sensores cadastrados. Quer cadastrar uma estação meteorológica no campo? Diga o nome e eu pergunto o resto.';
    }
    if (!items && !data) return 'Nenhum sensor encontrado.';
    return 'Não encontrei dados de sensores.';
  }

  // ── Genérico ──
  if (items && items.length > 0) {
    const nomes = items
      .slice(0, 5)
      .map(
        (i) =>
          i.nome || i.titulo || i.descricao || JSON.stringify(i).slice(0, 60).replace(/[{}"]/g, '')
      );
    return `Encontrei ${count} registro(s) de ${recurso}: ${nomes.join(', ')}.`;
  }
  if (count === 0 || (!items && Object.keys(data || {}).length === 0)) {
    return `Não encontrei dados de ${recurso} no sistema.`;
  }
  // último recurso: extrair campos sem mostrar JSON bruto
  const partes = [];
  for (const [k, v] of Object.entries(data || {})) {
    if (k.startsWith('_') || k === 'detail') continue;
    if (typeof v === 'string' || typeof v === 'number')
      partes.push(`${k.replace(/_/g, ' ')}: ${v}`);
    if (partes.length >= 6) break;
  }
  return partes.length
    ? `Dados de ${recurso}: ${partes.join(' | ')}`
    : `Dados de ${recurso} carregados com sucesso.`;
}

// ══════════════════════════════════════════════════════════════
// SMART RESPONSE — detecta intenção, busca dados, responde natural
// ══════════════════════════════════════════════════════════════
/**
 * Lê a previsão de `/api/previsao-clima/`, que NÃO é a mesma forma de
 * `/api/weather/`.
 *
 * `previsao_clima_data` delega a `ClimaService`, que fala o dialeto do
 * Open-Meteo: `{daily: {time: [...], temperature_2m_max: [...],
 * precipitation_sum: [...], precipitation_probability_max: [...]}}`. Já
 * `_get_real_weather` — o que `/api/weather/` devolve — fala
 * `{cidade, fonte, atual, previsao}`.
 *
 * Os dois iam para o MESMO formatador, que só lê a segunda forma. Uma
 * previsão com 7 dias completos caía em "não encontrei dados de previsão":
 * o formatador via um `undefined` e dizia que não havia nada, quando havia
 * tudo. Traduz-se aqui, para uma só forma, e o formatador continua a ter
 * uma responsabilidade só.
 */
function normalizarPrevisaoClima(payload) {
  if (!payload || typeof payload !== 'object') return payload;
  if (payload.atual || payload.previsao) return payload; // já é a forma comum

  const d = payload.daily;
  if (!d || !Array.isArray(d.time) || !d.time.length) return payload;

  const serie = (campo, i) => {
    const arr = d[campo];
    return Array.isArray(arr) && arr[i] != null ? Number(arr[i]) : null;
  };

  const dias = d.time.map((iso, i) => {
    const tmax = serie('temperature_2m_max', i);
    const tmin = serie('temperature_2m_min', i);
    const mm = serie('precipitation_sum', i);
    const prob = serie('precipitation_probability_max', i);
    return {
      dia: iso,
      // `temp` é o que o formatador lê. Quando só há máx/mín, a média é a
      // leitura honesta — é o número que alguém escolheria para dizer
      // "hoje". NUNCA 0: se nenhum dos dois veio, fica `null`, e `null` é
      // "a fonte não disse", que o formatador sabe dizer.
      temp: tmax != null && tmin != null ? (tmax + tmin) / 2 : (tmax ?? tmin ?? null),
      temp_max: tmax,
      temp_min: tmin,
      mm_chuva: mm,
      prob_chuva: prob,
      descricao: prob != null && prob >= 60 ? 'Chuva provável' : null,
    };
  });

  return {
    cidade: payload.cidade || payload.fonte_coordenadas_detalhe || '',
    fonte: payload.fonte || 'open-meteo',
    aviso_coordenadas: payload.aviso_coordenadas || null,
    atual: dias[0],
    previsao: dias,
  };
}

/**
 * A previsão do tempo, e o que se diz quando ela não vem.
 *
 * O defeito que corrigimos: as duas chamadas levavam `.catch(() => null)`,
 * e o `null` indistinguível levava a uma frase que culpava a estação
 * meteorológica — "Verifique a estação meteorológica". A estação era a
 * ÚLTIMA hipótese de quem escreveu, não a primeira. O servidor, esse, sabe
 * o motivo exacto: `previsao_clima_data` devolve 503 com um `erro` escrito
 * para o caso concreto ("cadastre a cidade/UF da propriedade…"). Esse texto
 * era deitado fora pelo `catch`, e substituído por uma acusação errada.
 *
 * A regra que fica: quando o servidor diz PORQUÊ, o produtor lê o PORQUÊ.
 * Uma falha sem motivo declarado não pode virar uma instrução inventada.
 */
/* A série dias×mm para o gráfico, no mesmo payload da prosa.
 *
 * Só quando o modo CRIAR está ligado e a pergunta é semanal: sem modo, a
 * resposta continua prosa pura (comportamento atual, sem surpresa); com
 * menos de 2 dias com mm, não há o que desenhar e a prosa já disse.
 * Rótulos sem locale (mapa próprio), como no servidor. */
const _DIAS_PT = ['dom', 'seg', 'ter', 'qua', 'qui', 'sex', 'sáb'];
function etiquetaDia(iso) {
  try {
    const d = new Date(String(iso || '').slice(0, 10) + 'T12:00:00');
    if (isNaN(d)) return String(iso || '').slice(5);
    const dd = String(d.getDate()).padStart(2, '0');
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    return _DIAS_PT[d.getDay()] + ' ' + dd + '/' + mm;
  } catch (e) {
    return String(iso || '');
  }
}
function anexaSerieClima(data) {
  try {
    if (!window.IaModos || typeof window.IaModos.activo !== 'function') return;
    if (!window.IaModos.activo('chat')) return;
    const dias = (data && data.previsao) || [];
    const linhas = [];
    for (const d of dias) {
      const mm = d && d.mm_chuva;
      if (mm === null || mm === undefined || isNaN(Number(mm))) continue;
      linhas.push([etiquetaDia(d.dia), Math.round(Number(mm) * 10) / 10]);
    }
    if (linhas.length < 2) return;
    window._sbSerie = {
      titulo: 'Chuva prevista por dia (mm)',
      rotulo: 'mm',
      colunas: ['dia', 'mm'],
      linhas: linhas.slice(0, 14),
      fonte: 'chuva-semana',
    };
  } catch (e) {}
}

async function buscarClimaWeb(opts) {
  let motivo = null;
  let ultimaFalha = null;

  for (const url of ['/api/previsao-clima/', '/api/weather/']) {
    try {
      const bruto = await apiFetch(url);
      const data = normalizarPrevisaoClima(bruto);
      if (data) {
        if (opts && opts.serie) anexaSerieClima(data);
        return formatarDadosNatural('clima', data);
      }
    } catch (e) {
      ultimaFalha = e;
      // A sessão morta é a ÚNICA falha em que insistir noutro endpoint
      // não pode mudar nada — e é a única em que redireccionar para o login
      // já foi feito pelo `apiFetch`.
      if (e && e.semSessao) {
        return '🔒 A sua sessão expirou. Entre novamente para eu ler o tempo da sua fazenda.';
      }
      // O servidor respondeu e disse o que falta. Guarda-se e usa-se.
      //
      // SÓ O PRIMEIRO MOTIVO CONTA. `/api/previsao-clima/` é o endpoint que
      // sabe a causa concreta — "cadastre a cidade/UF da propriedade, uma
      // estação, ou o GPS" — e `/api/weather/` devolve um genérico
      // "sem coordenada" para o mesmo problema. Deixar o último escrever
      // trocava a frase accionável pela que não diz o que fazer: o produtor
      // lia "sem coordenada" e não sabia o que preencher.
      if (!motivo && e && e.status === 503 && e.message) motivo = e.message;
    }
  }

  // O servidor disse porquê. Diz-se porquê, e diz-se o que fazer.
  if (motivo) {
    return `🌤️ Não tenho previsão para mostrar: ${motivo}\nDiga a cidade/UF da sua propriedade (ex: "minha fazenda é em Alterosa, MG") e eu busco o tempo daí.`;
  }

  // Nenhum dos dois respondeu, e nenhum disse porquê. Aí a honestidade é
  // dizer que não se sabe — e NÃO inventar uma estação para culpar.
  const detalhe = ultimaFalha && ultimaFalha.message ? ` (${ultimaFalha.message})` : '';
  return `🌤️ Não consegui consultar a previsão agora${detalhe}. Pode tentar outra vez, ou dizer a cidade/UF da fazenda que eu tento por outro caminho.`;
}

async function smartResponse(text) {
  const t = text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim();

  // ── Resposta (a)/(b)/(c) à pergunta de fonte de clima (ex: usuário digitou só "B") ──
  // (só casa a mensagem INTEIRA, para não sequestrar texto normal)
  //
  // ESTE BLOCO É O `iniciarCadastro` QUE FALTAVA, e é a razão de a conversa
  // do produtor ter morrido em "Entendi sua mensagem: estaçao met do lucas".
  //
  // `analisarIntent` reconhecia (a) e devolvia `tipo:'criar'`, `acao:'estacoes'`
  // e a pergunta "Nome da estação?". O `iaChat` imprimia a pergunta e seguia.
  // Imprimir uma pergunta de cadastro SEM abrir o cadastro é o defeito mais
  // caro desta camada: a pessoa escreve o nome, e não há máquina de estado
  // para o receber. A resposta seguinte não reconhece "estaçao met do lucas"
  // como campo nenhum — porque, para o sistema, nunca foi pedido, e é uma
  // pergunta de campo que não existe sozinha.
  //
  // `iaCadastroPendente` passa a existir em (a), e é ele que segura o nome na
  // mensagem seguinte (`avancarCadastro`). Sem isto, a pergunta era vã.
  const mOpcao = t.match(
    /^\s*(?:opcao|opção|letra)\s+([abc])\s*[).:]?\s*$|^\s*([abc])\s*[).:]?\s*$/
  );
  if (mOpcao) {
    const op = (mOpcao[1] || mOpcao[2] || '').toLowerCase();
    if (op === 'b') return await buscarClimaWeb();
    if (op === 'c') {
      try {
        const sData = await apiFetch(RECURSOS_API['sensores']);
        return formatarDadosNatural('sensores', sData);
      } catch (e) {
        // A sessão morta é o caso comum, e o `apiFetch` já-redireccionou.
        // Devolver o `detail` do DRF — "As credenciais de autenticação não
        // foram fornecidas" — é falar a língua do servidor com quem não a
        // entende, e sugere um problema de conta que não existe. A sessão
        // expirou; é isso que se diz, e é o que se resolve.
        if (e && e.semSessao) {
          return '🔒 A sua sessão expirou. Entre novamente para eu ver os sensores.';
        }
        return `Não consegui consultar os sensores agora${
          e?.message ? ` (${e.message})` : ''
        }. Tente de novo em instantes.`;
      }
    }
    // (a) — ABRIR o cadastro. Não só perguntar.
    return iniciarCadastro('estacoes');
  }

  // ── Clima / Chuva / Tempo ──
  if (t.match(/(chover|chuva|previsao|tempo|clima|temperatura|calor|frio|umidade|vento)/)) {
    // Pergunta semanal pede série para o gráfico (modo CRIAR ligado).
    // O `anexaSerieClima` decide sozinho se há modo e dias que prestem.
    const semana = /(semana|proximos dias|7 dias|sete dias|dia a dia)/.test(t);
    return await buscarClimaWeb(semana ? { serie: true } : undefined);
  }

  // ── Produção / Safra específica ──
  if (
    t.match(/(producao|produção|produzi|produzido|produtividade|colheita|colhi)/) ||
    t.match(/(quanto|total).*(produzi|colhi|safra)/)
  ) {
    try {
      // Tenta buscar dashboard primeiro (tem totais)
      const dash = await apiFetch('/api/dashboard/').catch(() => null);
      const safras = await apiFetch('/api/safras/').catch(() => null);
      const partes = [];
      if (dash && (dash.producao_total != null || dash.area_total != null)) {
        partes.push(formatarDadosNatural('dashboard', dash));
      }
      if (safras?.results?.length) {
        partes.push(formatarDadosNatural('safras', safras));
      }
      if (partes.length) return partes.join('\n\n');
    } catch {}
    return '🌱 Não encontrei dados de produção no sistema. Verifique se há safras cadastradas.';
  }

  // ── Fluxo de caixa / Financeiro ──
  if (t.match(/(fluxo.*caixa|caixa|financeiro|receita|despesa|saldo|lucro|prejuizo|balanco|dre)/)) {
    try {
      let data = await apiFetch('/api/financeiro/').catch(() => null);
      if (!data) data = await apiFetch('/api/financeiro/cashflow/').catch(() => null);
      if (data) return formatarDadosNatural('financeiro', data);
      // tenta lançamentos
      const lanc = await apiFetch('/api/lancamentos/').catch(() => null);
      if (lanc) return formatarDadosNatural('lancamentos', lanc);
    } catch {}
    return '💰 Não encontrei dados financeiros no sistema.';
  }

  // ── Cotações / Preço da saca ──
  if (
    t.match(
      /(preco|preço|saca|cotacao|cotação|commodity|valor).*(soja|milho|cafe|café|algod|trigo|arroz|boi|gado|sorgo)/
    ) ||
    t.match(
      /(soja|milho|cafe|café|algod|trigo|arroz|boi|gado|sorgo).*(preco|preço|saca|cotacao|cotação|valor)/
    )
  ) {
    try {
      const data =
        (await apiFetch('/api/commodities/').catch(() => null)) ||
        (await apiFetch('/api/financeiro/cotacoes/').catch(() => null));
      if (data) return formatarDadosNatural('commodities', data);
    } catch {}
    return '📊 Não encontrei cotações no momento.';
  }

  // ── Relatório ──
  if (t.match(/(relatorio|relatório|gerar.*relatorio|gerar.*relatório)/)) {
    let tipo = 'geral';
    if (t.includes('custo')) tipo = 'custo_producao';
    else if (t.includes('producao') || t.includes('produção')) tipo = 'producao';
    else if (t.includes('financeiro')) tipo = 'financeiro';
    else if (t.includes('estoque')) tipo = 'estoque';
    try {
      const res = await apiFetch('/api/relatorio/gerar/', {
        method: 'POST',
        body: JSON.stringify({ tipo, filtros: {} }),
      });
      return `📄 Relatório de ${tipo.replace(/_/g, ' ')} solicitado com sucesso! ${
        res?.id ? 'ID: ' + res.id : 'Aguarde o processamento.'
      }`;
    } catch (e) {
      return `Não consegui gerar o relatório: ${e.message}. Verifique na página de relatórios.`;
    }
  }

  // ── Cadastros / "quais cadastros tenho" ──
  if (t.match(/quais.*(cadastro|registro|talh|safra|cultura|cafe|café|soja|milho)/)) {
    // Detecta o que quer consultar
    const mapConsulta = [
      [/(cafe|café)/, 'culturas'],
      [/(soja|milho|algod|trigo|arroz)/, 'culturas'],
      [/cultura/, 'culturas'],
      [/talh/, 'talhoes'],
      [/safra/, 'safras'],
      [/funcion/, 'funcionarios'],
      [/insumo/, 'insumos'],
      [/maquin/, 'maquinarios'],
      [/animal/, 'animais'],
      [/estoque/, 'estoque'],
      [/propried|fazenda/, 'propriedades'],
    ];
    let recurso = 'culturas'; // default
    for (const [regex, rec] of mapConsulta) {
      if (t.match(regex)) {
        recurso = rec;
        break;
      }
    }
    try {
      const url = RECURSOS_API[recurso] || `/api/${recurso}/`;
      const data = await apiFetch(url);
      return formatarDadosNatural(recurso, data);
    } catch (e) {
      return `Não consegui consultar ${recurso}: ${e.message}`;
    }
  }

  // ── Consulta genérica de dados ──
  if (t.match(/(mostrar|ver|listar|consultar|puxar|exibir|buscar|quantos|quanto)\s/)) {
    const mapConsulta = [
      [/estoque/, 'estoque'],
      [/(financeiro|lanc|caixa)/, 'lancamentos'],
      [/safra/, 'safras'],
      [/talh/, 'talhoes'],
      [/(propried|fazenda)/, 'propriedades'],
      [/cultura/, 'culturas'],
      [/insumo/, 'insumos'],
      [/(maquin|trator|caminho|caminh)/, 'maquinarios'],
      [/funcion/, 'funcionarios'],
      [/animal/, 'animais'],
      [/sensor/, 'sensores'],
      [/(opera|tarefa)/, 'operacoes'],
    ];
    for (const [regex, recurso] of mapConsulta) {
      if (t.match(regex)) {
        try {
          const url = RECURSOS_API[recurso] || `/api/${recurso}/`;
          const data = await apiFetch(url);
          return formatarDadosNatural(recurso, data);
        } catch (e) {
          return `Não consegui consultar ${recurso}: ${e.message}`;
        }
      }
    }
  }

  // ── Tarefas/agenda do dia ──
  if (
    t.match(/(tarefas|agenda|operacoes|operacoes).*(hoje|dia|agora)/) ||
    t.match(/quais.*tarefas/)
  ) {
    try {
      const hoje = new Date().toISOString().slice(0, 10);
      const data = await apiFetch(`/api/operacoes/?data_agendada=${hoje}`);
      return formatarDadosNatural('operacoes', data);
    } catch (e) {
      return `Não consegui consultar a agenda: ${e.message}`;
    }
  }

  // ── Configurar / instalar estação meteorológica ──
  if (
    t.match(/(configurar|instalar|criar|cadastrar|adicionar).*(estacao|estação|meteo|meteorolog)/)
  ) {
    return iniciarCadastro('estacoes');
  }

  // ── Configurar / cadastrar genérico ──
  // O verbo aparece conjugado de formas que o `if` exterior nao previa:
  // "como se adiciona" (não "adicionar"), "como se registra" (não
  // "registrar"). Um verbo conjugado e' a forma NORMAL de uma pergunta —
  // e' o infinitivo que e' a excepcao.
  if (t.match(/(configur|cadastr|criar|adicion|inser|regist|nova|novo|registo)/)) {
    const mapCadastro = [
      [/(estacao|estação|meteo|meteorolog)/, 'estacoes'],
      [/funcion/, 'funcionarios'],
      [/safra/, 'safras'],
      [/talh/, 'talhoes'],
      [/estoque/, 'estoque'],
      [/(opera|tarefa)/, 'operacoes'],
      [/insumo/, 'insumos'],
      [/cultura/, 'culturas'],
      [/(propried|fazenda)/, 'propriedades'],
      // `maquinanarios` NAO existe em ESQUEMAS_CADASTRO.
      //
      // Apontar para um recurso inexistente fazia a linha seguinte
      // devolver "Posso criar maquinarios para você. Me diga os dados que
      // deseja cadastrar" — e depois nao ha dados para pedir: o
      // formulario nao existe. E' a promessa vazia, que e' pior que o
      // "nao percebi": pelo menos o "nao percebi" obriga a pessoa a tentar
      // outra frase.
      //
      // A correccao honesta e' o esquema de maquinas existir — o backend
      // tem `cadastrar_maquina` — e nao o mapa prometer o que o frontend
      // nao sabe fazer. ate la, "adicionar trator" cai na pergunta abaixo.
    ];
    for (const [regex, recurso] of mapCadastro) {
      if (t.match(regex)) {
        if (ESQUEMAS_CADASTRO[recurso]) return iniciarCadastro(recurso);
        return `Posso criar ${recurso} para você. Me diga os dados que deseja cadastrar.`;
      }
    }
    // O VERBO ESTÁ, O RECURSO NÃO.
    //
    // "como se cadastrar" passa no `t.match(/cadastrar/)` acima, mas não
    // contém nenhuma das dez palavras de recurso: "cadastrar" não tem
    // "funcion", não tem "safra", não tem "talh". O loop não casa, e a
    // função saía com `return null` — que é o fallback genérico, o
    // "Entendi sua mensagem: ... Como posso ajudar?".
    //
    // A pergunta era legítima e a resposta devia ser uma pergunta: o que é
    // que queres criar? A alternativa — escolher um recurso por defeito —
    // seria inventar o que a pessoa queria, que é o defeito que esta
    // camada existe para evitar.
    //
    // O guarda tem duas partes, e as duas importam.
    //
    // A interrogação: "qual o registo", "como se cadastra". Sem isto, uma
    // pergunta so passava se terminasse em verbo, e "qual o registo" nao
    // termina em verbo nenhum.
    //
    // A intencao de criar: "como se cadastrar" tem verbo; "adicionar
    // trator" tambem. Mas exige que a frase NAO contenha palavra de
    // recurso — se contiver, o `for` acima ja devolveu. Chegar aqui e'
    //_signal_ que o verbo apareceu sem dizer o que.
    const pergunta = /^(como|onde|quando|qual|quais|que|o que|aonde)\b/.test(t);
    if (pergunta || querCriarSemRecurso(t)) {
      // TODOS os recursos, nao os primeiros seis: uma lista truncada
      // esconde o recurso que a pessoa queria, e ela acaba por escolher
      // um dos seis por ser o unico que conhece. Nove nomes cabem numa
      // frase; a lista parcial e' a que obriga a adivinhar.
      const recursos = Object.keys(ESQUEMAS_CADASTRO);
      return (
        `Posso criar ${recursos.length} tipos de registo. Qual queres criar? ` +
        `${recursos.join(', ')}.`
      );
    }
  }

  return null; // não detectou intenção — passa para próximo handler
}

// A pessoa disse que quer criar, mas nao disse O QUÊ.
//
// Fica como função à parte, e não dentro do handler, porque é uma regra
// sobre a frase — não sobre o que o handler já fez. E porque o teste
// (unit/ia_cadastro_sem_recurso.test.js) a invoca com frases isoladas, sem
// ter de montar um `ESQUEMAS_CADASTRO` inteiro para a testar.
//
// "adicionar trator" diz querer criar e não diz o que. Não há "maquina" no
// mapa porque não há formulário de maquinas; há "trator", que era o termo
// mais específico que existia, e que por isso acabava a prometer um
// formulário que não existe.
function querCriarSemRecurso(t) {
  return /(cadastr|criar|adicion|regist|inser|configur|nova|novo)/.test(t);
}

// ══════════════════════════════════════════════════════════════
// SANITIZADOR — nunca mostrar JSON/código ao usuário
// ══════════════════════════════════════════════════════════════
function sanitizarResposta(text) {
  if (!text || typeof text !== 'string') return text;
  let t = text.trim();
  // Remove blocos JSON completos (incluindo aninhados)
  t = t.replace(/\{(?:[^{}]|\{[^{}]*\})*\}/g, '').trim();
  // Remove blocos de código
  t = t.replace(/```[\s\S]*?```/g, '').trim();
  // Remove chaves/colchetes soltos
  t = t.replace(/[{}\[\]]/g, '').trim();
  // Remove linhas que parecem JSON ou código
  t = t
    .split('\n')
    .filter((line) => {
      const l = line.trim();
      return (
        l &&
        !l.startsWith('"') &&
        !l.startsWith('{') &&
        !l.startsWith('}') &&
        !l.match(/^["']\w+["']\s*:/)
      );
    })
    .join('\n')
    .trim();
  // Se ficou vazio após limpeza
  if (!t) return 'Entendi! Como posso ajudar?';
  return t;
}
/* ═══════════════════════════════════════════════════════════
   WIZARD ANIMAL — lote/rebanho com checklist [✓]
   espécie → tipo (corte/leite/ovos) → raça → cabeças → peso →
   entrada → cria → piquete e/ou produção (leite/ovos).
   ═══════════════════════════════════════════════════════════ */
let wizAnimal = null;
const WIZ_ESPECIES_ANIMAL = [
  {
    code: 'BOVINO',
    label: 'Bovino',
    cultura: 'Boi Gordo',
    keys: [
      'bovino',
      'boi',
      'vaca',
      'bezerro',
      'novilh',
      'gado',
      'nelore',
      'angus',
      'holand',
      'girolando',
      'guzera',
    ],
  },
  {
    code: 'SUINO',
    label: 'Suíno',
    cultura: 'Suíno',
    keys: ['suino', 'suina', 'porco', 'leitao', 'matriz'],
  },
  {
    code: 'OVINO',
    label: 'Ovino',
    cultura: 'Ovino',
    keys: ['ovino', 'ovelha', 'carneiro', 'borrego'],
  },
  { code: 'CAPRINO', label: 'Caprino', cultura: 'Caprino', keys: ['caprino', 'cabra', 'bode'] },
  {
    code: 'EQUINO',
    label: 'Equino',
    cultura: 'Equino',
    keys: ['equino', 'cavalo', 'egua', 'potro'],
  },
  { code: 'BUFALO', label: 'Búfalo', cultura: 'Búfalo', keys: ['bufalo', 'bubalino'] },
  {
    code: 'AVES',
    label: 'Aves',
    cultura: 'Frango',
    keys: ['ave', 'frango', 'galinha', 'peru', 'codorna', 'marreco', 'pato', 'poedeira'],
  },
  { code: 'COELHO', label: 'Coelho', cultura: null, keys: ['coelho'] },
];
const WIZ_TIPOS_ANIMAL = [
  { code: 'CORTE', keys: ['corte', 'engorda', 'abate'] },
  { code: 'LEITE', keys: ['leite', 'ordenha'] },
  { code: 'OVOS', keys: ['ovo', 'postura', 'poedeira'] },
  { code: 'MISTO', keys: ['misto', 'ambos'] },
  { code: 'MEL', keys: ['mel', 'apicultura', 'abelha'] },
];
function wizAnimalTrigger(t) {
  if (wizEhInterrogacao(t)) return false;
  const n = wizNorm(t);
  if (
    !/(animal|rebanho|gado|boi|vaca|bezerro|novilh|suino|suina|matriz|leitao|porco|ovino|ovelha|caprino|cabra|equino|cavalo|bufalo|frango|galinha|aves|coelho|leite|ovos|piquete)/.test(
      n
    )
  )
    return false;
  return /cadastr|cria\w*|crie|nov[oa]|adicion|registr|comec|inici/.test(n);
}
function wizEspecieAnimal(t) {
  const n = wizNorm(t);
  return WIZ_ESPECIES_ANIMAL.find((e) => e.keys.some((k) => n.includes(k))) || null;
}
function wizTipoAnimal(t) {
  const n = wizNorm(t);
  const hit = WIZ_TIPOS_ANIMAL.find((x) => x.keys.some((k) => n.includes(k)));
  return hit ? hit.code : null;
}
function wizAnimalChecklist(a) {
  const L = [];
  L.push((a.especie ? '[✓]' : '[ ]') + ' Espécie' + (a.especie ? ': ' + a.especie.label : ''));
  L.push((a.tipo ? '[✓]' : '[ ]') + ' Produção' + (a.tipo ? ': ' + a.tipo.toLowerCase() : ''));
  L.push(
    (a.raca !== undefined && a.raca !== null ? '[✓]' : '[ ]') +
      ' Raça' +
      (a.raca ? ': ' + a.raca : '')
  );
  L.push((a.qtd ? '[✓]' : '[ ]') + ' Cabeças' + (a.qtd ? ': ' + a.qtd : ''));
  L.push(
    (a.data ? '[✓]' : '[ ]') +
      ' Entrada' +
      (a.data ? ': ' + a.data.split('-').reverse().join('/') : '')
  );
  return L.join('\n');
}
async function wizNavegarAnimal(a) {
  if (!a.especie || !a.especie.cultura) return;
  try {
    const list = await wizList('/api/culturas/');
    const hit = list.find((c) => wizNorm(c.nome).includes(wizNorm(a.especie.cultura)));
    if (!hit) return;
    if (typeof window.safeShowCulturaDetail === 'function')
      window.safeShowCulturaDetail(hit.id, hit.nome, 'animal');
    else if (typeof window.showCulturaDetail === 'function')
      window.showCulturaDetail(hit.id, hit.nome, 'animal');
  } catch {}
}
function wizAnimalStart() {
  wizAnimal = {
    step: 'especie',
    especie: null,
    tipo: null,
    raca: null,
    qtd: null,
    peso: null,
    data: null,
    lote: null,
  };
  return 'Vamos cadastrar um lote! 🐄\n[ ] Espécie\n[ ] Produção\n[ ] Raça\n[ ] Cabeças\n[ ] Entrada\n\nQual a espécie? (boi, suíno, ovino, frango…)';
}
async function wizAnimalStep(texto) {
  const a = wizAnimal;
  const t = (texto || '').trim();
  if (wizCancelar(t)) {
    wizAnimal = null;
    return 'Fluxo cancelado. Quando quiser, é só dizer "cadastrar rebanho".';
  }
  const _g = await wizGuardas(WIZ_META.animal, 'animal', texto);
  if (_g) return _g;
  if (a.step === 'especie') {
    const e = wizEspecieAnimal(t);
    if (!e) {
      if (/peixe|tilapia|tambaqui|camarao/.test(wizNorm(t))) {
        return 'Peixe é no fluxo aquático! 🐟 Diga "cadastrar peixe" que eu te levo pra lá. Qual a espécie do lote? (boi, suíno, ovino, frango…)';
      }
      return 'Não identifiquei. Opções: bovino, suíno, ovino, caprino, equino, búfalo, aves, coelho. Qual a espécie?';
    }
    a.especie = e;
    a.step = 'tipo';
    wizNavegarAnimal(a);
    return `${wizAnimalChecklist(a)}\n\n${
      e.label
    } — abri a guia animal. Qual o tipo de produção? (corte, leite, ovos — Enter = corte)`;
  }
  if (a.step === 'tipo') {
    if (!t) {
      a.tipo = 'CORTE';
    } else {
      const tipo = wizTipoAnimal(t);
      if (!tipo) return 'Não entendi — é corte, leite, ovos ou misto? (Enter = corte)';
      a.tipo = tipo;
    }
    a.step = 'raca';
    return `${wizAnimalChecklist(a)}\n\nQual a raça? (Enter = pular)`;
  }
  if (a.step === 'raca') {
    const n = wizNorm(t);
    if (wizSim(t) || wizNao(t)) return 'Qual a raça? (diga o nome — ou "pular")';
    a.raca = !t || /pular|sem raca|nao sei|mesti/.test(n) ? null : t;
    a.step = 'qtd';
    return `${wizAnimalChecklist(a)}\n\nQuantas cabeças?`;
  }
  if (a.step === 'qtd') {
    const num = wizParseNum(t);
    if (!num || num <= 0)
      return 'Preciso da quantidade de cabeças (ex: 20 — pode escrever "vinte"). Quantas?';
    if (num > 100000) {
      const nq = Math.round(num);
      return wizArmarConfirm(
        WIZ_META.animal,
        `⚠️ ${nq} cabeças é um rebanho gigante — confirma que é isso mesmo? (sim/não)`,
        async () => {
          a.qtd = nq;
          a.step = 'peso';
          return `${wizAnimalChecklist(a)}\n\nPeso médio em kg? (Enter = pular)`;
        },
        'Ok, quantas cabeças?'
      );
    }
    a.qtd = Math.round(num);
    a.step = 'peso';
    return `${wizAnimalChecklist(a)}\n\nPeso médio em kg? (Enter = pular)`;
  }
  if (a.step === 'peso') {
    let num = wizParseNum(t);
    if (num && /arroba/.test(wizNorm(t))) num = num * 15; // 1 arroba = 15 kg
    if (num && num > 2000) {
      return wizArmarConfirm(
        WIZ_META.animal,
        `⚠️ ${num} kg de média por animal é bem alto — confirma? (sim/não)`,
        async () => {
          a.peso = num;
          a.step = 'data';
          return `${wizAnimalChecklist(a)}\n\nData de entrada? (dd/mm/aaaa — ou diga "hoje")`;
        },
        'Ok, qual o peso médio em kg? (ou Enter para pular)'
      );
    }
    a.peso = num && num > 0 ? num : null;
    a.step = 'data';
    return `${wizAnimalChecklist(a)}\n\nData de entrada? (dd/mm/aaaa — ou diga "hoje")`;
  }
  if (a.step === 'data') {
    const d = wizParseDatas(t);
    // A data de ENTRADA do animal nao e' hoje quando o produtor nao sabe.
    // `wizHoje()` le o relogio — e usar o relogio como resposta a "quando?"
    // e' fabricar uma medicao que vai para `data_entrada` e dai para custo,
    // DRE e rastreabilidade. Mesma classe que `f.step === 'admissao'`.
    //
    // A correccao e PERGUNTAR, e nao inventar outra data. A unica excepcao
    // legitima a "hoje" e o produtor DIZER "hoje" — e `wizDataRelativa`
    // (usada no wizard de tarefa) resolve isso sem tocar no relogio as cegas.
    if (!d.length) {
      const dRel = t ? wizDataRelativa(t) : null;
      if (!dRel) {
        a.step = 'data';
        return 'Qual a data de entrada? (dd/mm/aaaa — ou diga "hoje" se foi hoje)';
      }
      const criar = async () => {
        a.data = dRel;
        const propId = await wizPropAnimal(a);
        try {
          const payload = {
            propriedade: propId,
            especie: a.especie.code,
            tipo_producao: a.tipo,
            quantidade: a.qtd,
            data_entrada: a.data,
          };
          if (a.raca) payload.raca = a.raca;
          if (a.peso) payload.peso_medio = a.peso;
          const created = await apiFetch('/api/animais/', {
            method: 'POST',
            body: JSON.stringify(payload),
          });
          a.lote = created;
          a.step = 'ramo';
          return `${wizAnimalChecklist(a)}\n\nPronto, lote criado! 🐂 ${a.qtd} ${a.especie.label.toLowerCase()} (${a.tipo.toLowerCase()}, entrada ${wizFmtData(a.data)}).\nQuer cadastrar um piquete pra eles, registrar produção (leite/ovos), ou fechar?`;
        } catch (e) {
          return `Não consegui criar o lote: ${e.message}. Quantas cabeças?`;
        }
      };
      return wizArmarConfirm(
        WIZ_META.animal,
        'Registar o animal com esta data?',
        criar,
        'Ok, qual a data? (dd/mm/aaaa)'
      );
    }
    const dataIso = d[0];
    const criar = async () => {
      a.data = dataIso;
      const propId = await wizPropAnimal(a);
      try {
        const payload = {
          propriedade: propId,
          especie: a.especie.code,
          tipo_producao: a.tipo,
          quantidade: a.qtd,
          data_entrada: a.data,
        };
        if (a.raca) payload.raca = a.raca;
        if (a.peso) payload.peso_medio = a.peso;
        const created = await apiFetch('/api/animais/', {
          method: 'POST',
          body: JSON.stringify(payload),
        });
        a.lote = created;
        a.step = 'ramo';
        return `${wizAnimalChecklist(a)}\n\nPronto, lote criado! ✅ ${
          a.qtd
        } ${a.especie.label.toLowerCase()} (${a.tipo.toLowerCase()}, entrada ${wizFmtData(
          a.data
        )}).\nQuer cadastrar um piquete pra eles, registrar produção (leite/ovos), ou fechar?`;
      } catch (e) {
        return `Não consegui criar o lote: ${e.message}. Quantas cabeças?`;
      }
    };
    if (dataIso > hoje) {
      return wizArmarConfirm(
        WIZ_META.animal,
        `⚠️ ${wizFmtData(dataIso)} é uma data futura — é um pré-cadastro? (sim/não)`,
        criar,
        'Ok, qual a data de entrada? (dd/mm/aaaa — ou diga "hoje")'
      );
    }
    return await criar();
  }
  if (a.step === 'ramo') {
    const n = wizNorm(t);
    if (wizAquaTrigger(t)) {
      wizAnimal = null;
      return wizAquaStart();
    }
    if (wizTrigger(t)) {
      wizAnimal = null;
      return wizSafraStart(typeof t !== 'undefined' ? t : lastUser);
    }
    if (typeof wizTalhaoTrigger === 'function' && wizTalhaoTrigger(t)) {
      wizAnimal = null;
      return wizTalhaoStart(t);
    }
    if (typeof wizFuncRemTrigger === 'function' && wizFuncRemTrigger(t)) {
      wizAnimal = null;
      return wizFuncRemStart(t);
    }
    if (typeof wizFuncTrigger === 'function' && wizFuncTrigger(t)) {
      wizAnimal = null;
      return wizFuncStart(t);
    }
    if (typeof wizTarefaTrigger === 'function' && wizTarefaTrigger(t)) {
      wizAnimal = null;
      return wizTarefaStart(t);
    }
    if (wizSim(t)) return 'Diga um dos três: piquete, produção ou fechar?';
    if (/piquete|pasto|potreiro/.test(n)) {
      a.step = 'piq_nome';
      return 'Qual o nome do piquete? (ex: Piquete 1)';
    }
    if (/producao|produção|leite|ovos|ordenha|postura/.test(n)) {
      a.step = 'prod_data';
      return 'Vamos registrar a produção. Qual a data? (dd/mm/aaaa — ou diga "hoje")';
    }
    if (/fechar|pronto|chega|nao|depois|por enquanto/.test(n)) {
      wizAnimal = null;
      return 'Fechado! ✅ Lote salvo. Se precisar: piquete, produção, pesagem ou sanidade — é só chamar.';
    }
    return 'Quer cadastrar um piquete, registrar produção, ou fechar?';
  }
  if (a.step === 'piq_nome') {
    if (!t) return 'Qual o nome do piquete?';
    // A pergunta NAO e' o nome. `wizEhPergunta` é o que separa "Pastagem -
    // Braquiaria" de "qual pastagem temos" — e sem esta guarda o cadastro
    // grava a própria pergunta como nome do piquete. Um erro visível, que se
    // corrige; pior do que a data inventada, porque aqui não há nem
    // placeholder.
    if (wizNaoEhValor(t)) return 'Qual o nome do piquete? (ex: Piquete 1, Pasto Sul)';
    a.piqNome = t;
    a.step = 'piq_area';
    return `Piquete "${t}". Qual a área em ha?`;
  }
  if (a.step === 'piq_area') {
    const num = wizParseNum(t);
    if (!num || num <= 0) return 'Qual a área do piquete em ha? (ex: 5)';
    a.piqArea = num;
    a.step = 'piq_cap';
    return 'Qual a capacidade em UA/ha? (Enter = 1,0)';
  }
  if (a.step === 'piq_cap') {
    const num = wizParseNum(t);
    const cap = num && num > 0 ? num : 1.0;
    if (cap > 10) {
      return wizArmarConfirm(
        WIZ_META.animal,
        `⚠️ ${cap} UA/ha é uma lotação bem alta — confirma? (sim/não)`,
        async () => {
          a.piqCap = cap;
          a.step = 'piq_talhao';
          return 'Esse piquete fica em qual talhão? (nome — ou Enter para pular)';
        },
        'Ok, qual a capacidade em UA/ha? (ou Enter = 1,0)'
      );
    }
    a.piqCap = cap;
    a.step = 'piq_talhao';
    return 'Esse piquete fica em qual talhão? (nome — ou Enter para pular)';
  }
  if (a.step === 'piq_talhao') {
    let talhaoId = null;
    if (t && !/pular/.test(wizNorm(t))) {
      const list = await wizList('/api/talhoes/');
      const r = wizEscolher(list, t);
      if (r.alternativa.length) {
        return `Achei ${r.alternativa.length}: ${wizNomes(r.alternativa, 5).join(
          ', '
        )}. Qual deles? (ou Enter para pular)`;
      }
      if (!r.tal) {
        const porPergunta = wizEhPergunta(t)
          ? wizComPergunta('esse talhão', list, 'Esse piquete fica em qual talhão?', 'talhão')
          : null;
        if (porPergunta) return porPergunta;
        if (a._talhaoRetryCount === undefined) a._talhaoRetryCount = 0;
        a._talhaoRetryCount++;
        if (a._talhaoRetryCount >= 2) {
          a.step = 'pos';
          return `Sem problema — vamos seguir sem talhão. Você pode cadastrar um depois.\n\nPiquete "${a.piqNome}" será criado sem talhão vinculado. O que mais?`;
        }
        return wizSemAcerto('esse talhão', list, t, 'talhão');
      }
      talhaoId = r.tal.id;
    }
    const criar = async () => {
      try {
        const payload = {
          propriedade: await wizPropAnimal(a),
          nome: a.piqNome,
          area_hectare: a.piqArea,
          capacidade_ua_ha: a.piqCap,
        };
        if (talhaoId) payload.talhao = talhaoId;
        await apiFetch('/api/piquetes/', { method: 'POST', body: JSON.stringify(payload) });
        a.step = 'pos';
        return `Piquete "${a.piqNome}" criado! ✅ (${a.piqArea} ha, ${a.piqCap} UA/ha)\nO que mais? (produção, outro piquete, ou fechar)`;
      } catch (e) {
        a.step = 'pos';
        return `Não consegui criar o piquete: ${e.message}. O que mais?`;
      }
    };
    try {
      const list = await wizList('/api/piquetes/');
      const dup = list.find((p) => wizNorm(p.nome) === wizNorm(a.piqNome));
      if (dup) {
        return wizArmarConfirm(
          WIZ_META.animal,
          `⚠️ Já existe um piquete "${a.piqNome}". Criar outro mesmo assim? (sim/não)`,
          criar,
          'Ok — qual o nome do piquete? (diga "voltar" pra corrigir)'
        );
      }
    } catch {}
    return await criar();
  }
  if (a.step === 'prod_data') {
    const d = wizParseDatas(t);
    // NUNCA `d.length ? d[0] : wizHoje()`.
    //
    // MEDIDO, 2026-10-04: existiam SEIS sitios com este fallback — e cada um
    // gravava uma data que ninguem forneceu. `wizHoje()` e' uma funcao que le
    // o relogio; usar o relogio como resposta a "quando?" e fabricar uma
    // medicao. Ver a nota longa em `f.step === 'admissao'`.
    //
    // A data de producao animal e' a pior das seis: entra num
    // `ProducaoAnimal` que alimenta custo de producao, DRE e rastreabilidade.
    if (!d.length) {
      a.step = 'prod_data';
      return 'Qual a data da produção? (dd/mm/aaaa)';
    }
    const dataIso = d[0];
    if (dataIso > wizHoje()) {
      return wizArmarConfirm(
        WIZ_META.animal,
        `📅 ${wizFmtData(dataIso)} ainda nem chegou - é um lançamento previsto? (sim/não)`,
        async () => {
          a.prodData = dataIso;
          a.step = 'prod_qtd';
          return 'Quantidade e unidade? (ex: 120 litros, 30 dúzias, 45 kg)';
        },
        'Ok, qual a data da produção? (dd/mm/aaaa)'
      );
    }
    a.prodData = dataIso;
    a.step = 'prod_qtd';
    return 'Quantidade e unidade? (ex: 120 litros, 30 dúzias, 45 kg)';
  }
  if (a.step === 'prod_qtd') {
    const num = wizParseNum(t);
    if (!num || num <= 0) return 'Quantidade e unidade? (ex: 120 litros, 30 dúzias, 45 kg)';
    a.prodQtd = num;
    const um = String(t || '').match(/([a-zA-Z%][a-zA-Zçãõéêúíóáàü\s%/]*)/);
    a.prodUn =
      (um ? um[1].trim() : '') || (a.tipo === 'LEITE' ? 'L' : a.tipo === 'OVOS' ? 'dz' : 'kg');
    a.step = 'prod_valor';
    return `Anotado: ${num} ${a.prodUn}. Valor estimado em R$? (Enter = pular)`;
  }
  if (a.step === 'prod_valor') {
    const num = wizParseNum(t);
    const salvar = async (valor) => {
      try {
        const payload = {
          animal: a.lote.id,
          data: a.prodData,
          quantidade_produzida: a.prodQtd,
          unidade: a.prodUn,
        };
        if (valor && valor > 0) payload.valor_estimado = valor;
        await apiFetch('/api/producao-animal/', { method: 'POST', body: JSON.stringify(payload) });
        a.step = 'pos';
        return `Produção registrada! ✅ ${a.prodQtd} ${a.prodUn} (${wizFmtData(
          a.prodData
        )}).\nO que mais? (outra produção, piquete, ou fechar)`;
      } catch (e) {
        a.step = 'pos';
        return `Não consegui registrar: ${e.message}. O que mais?`;
      }
    };
    if (num && num > 100000000) {
      return wizArmarConfirm(
        WIZ_META.animal,
        `⚠️ R$ ${num} é um valor bem alto — confirma? (sim/não)`,
        () => salvar(num),
        'Ok, qual o valor estimado em R$? (ou Enter para pular)'
      );
    }
    return await salvar(num);
  }
  if (a.step === 'pos') {
    const n = wizNorm(t);
    if (wizAquaTrigger(t)) {
      wizAnimal = null;
      return wizAquaStart();
    }
    if (wizTrigger(t)) {
      wizAnimal = null;
      return wizSafraStart(typeof t !== 'undefined' ? t : lastUser);
    }
    if (typeof wizTalhaoTrigger === 'function' && wizTalhaoTrigger(t)) {
      wizAnimal = null;
      return wizTalhaoStart(t);
    }
    if (typeof wizFuncRemTrigger === 'function' && wizFuncRemTrigger(t)) {
      wizAnimal = null;
      return wizFuncRemStart(t);
    }
    if (typeof wizFuncTrigger === 'function' && wizFuncTrigger(t)) {
      wizAnimal = null;
      return wizFuncStart(t);
    }
    if (typeof wizTarefaTrigger === 'function' && wizTarefaTrigger(t)) {
      wizAnimal = null;
      return wizTarefaStart(t);
    }
    if (/piquete|pasto/.test(n)) {
      a.step = 'piq_nome';
      return 'Qual o nome do piquete?';
    }
    if (/producao|produção|leite|ovos|ordenha/.test(n)) {
      a.step = 'prod_data';
      return 'Qual a data da produção? (dd/mm/aaaa — ou diga "hoje")';
    }
    if (/novo lote|outro lote|cadastrar/.test(n)) return wizAnimalStart();
    wizAnimal = null;
    return 'Fechado! ✅ Se precisar, é só chamar: lote, piquete ou produção.';
  }
  wizAnimal = null;
  return 'Vamos recomeçar: diga "cadastrar rebanho".';
}
async function wizPropAnimal(a) {
  if (window._iaPropPadrao) return window._iaPropPadrao;
  try {
    const j = await apiFetch('/api/propriedades/');
    const list = j.results || [];
    if (list.length) {
      window._iaPropPadrao = list[0].id;
      return list[0].id;
    }
  } catch {}
  return null;
}

/* ═══════════════════════════════════════════════════════════
   WIZARD AQUÁTICO — lote de peixes/camarão com checklist [✓]
   espécie → sistema → ambiente → quantidade → biomassa →
   povoamento → cria → despesca.
   ═══════════════════════════════════════════════════════════ */
let wizAqua = null;
const WIZ_ESPECIES_AQUA = [
  { code: 'TILAPIA', label: 'Tilápia', cultura: 'Peixe (Tilápia)', keys: ['tilapia'] },
  { code: 'TAMBAQUI', label: 'Tambaqui', cultura: 'Peixe (Tambaqui)', keys: ['tambaqui'] },
  { code: 'CARPA', label: 'Carpa', cultura: 'Peixe (Carpa)', keys: ['carpa'] },
  { code: 'PIRARUCU', label: 'Pirarucu', cultura: 'Peixe (Pirarucu)', keys: ['pirarucu'] },
  { code: 'TRUTA', label: 'Truta', cultura: 'Peixe (Truta)', keys: ['truta'] },
  { code: 'PINTADO', label: 'Pintado', cultura: null, keys: ['pintado'] },
  { code: 'CAMARAO', label: 'Camarão', cultura: 'Camarão', keys: ['camarao', 'camar'] },
  {
    code: 'OUTRO_PEIXE',
    label: 'Outro peixe',
    cultura: null,
    keys: ['peixe', 'pacu', 'jundia', 'curimata', 'lambari'],
  },
  {
    code: 'OUTRO_CRUSTACEO',
    label: 'Outro crustáceo',
    cultura: null,
    keys: ['crustaceo', 'lagosta', 'siri'],
  },
];
const WIZ_SISTEMAS_AQUA = [
  { code: 'VIVEIRO_ESCAVADO', keys: ['viveiro', 'escavado', 'acude', 'açude'] },
  { code: 'TANQUE_REDE', keys: ['tanque rede', 'rede'] },
  { code: 'TANQUE_ELEVADO', keys: ['tanque elevado', 'caixa', 'elevado'] },
  { code: 'AQUAPONIA', keys: ['aquaponia'] },
  { code: 'BIOFLOCOS', keys: ['biofloco', 'bft'] },
];
function wizAquaTrigger(t) {
  if (wizEhInterrogacao(t)) return false;
  const n = wizNorm(t);
  if (
    !/(peixe|tilapia|tambaqui|pacu|carpa|truta|pintado|pirarucu|jundia|curimata|camarao|aquatico|aquicola|tanque|viveiro|despesca|povoamento)/.test(
      n
    )
  )
    return false;
  return /cadastr|cria\w*|crie|nov[oa]|adicion|registr|comec|inici/.test(n);
}
function wizEspecieAqua(t) {
  const n = wizNorm(t);
  return WIZ_ESPECIES_AQUA.find((e) => e.keys.some((k) => n.includes(k))) || null;
}
function wizSistemaAqua(t) {
  const n = wizNorm(t);
  const hit = WIZ_SISTEMAS_AQUA.find((s) => s.keys.some((k) => n.includes(k)));
  return hit ? hit.code : null;
}
function wizAquaChecklist(q) {
  const L = [];
  L.push((q.especie ? '[✓]' : '[ ]') + ' Espécie' + (q.especie ? ': ' + q.especie.label : ''));
  L.push(
    (q.sistema ? '[✓]' : '[ ]') +
      ' Sistema' +
      (q.sistema ? ': ' + q.sistema.replace(/_/g, ' ').toLowerCase() : '')
  );
  L.push(
    (q.ambiente !== undefined && q.ambiente !== null ? '[✓]' : '[ ]') +
      ' Ambiente' +
      (q.ambiente ? ': ' + q.ambiente : '')
  );
  L.push((q.qtd ? '[✓]' : '[ ]') + ' Quantidade' + (q.qtd ? ': ' + q.qtd : ''));
  L.push(
    (q.data ? '[✓]' : '[ ]') +
      ' Povoamento' +
      (q.data ? ': ' + q.data.split('-').reverse().join('/') : '')
  );
  return L.join('\n');
}
async function wizNavegarAqua(q) {
  if (!q.especie || !q.especie.cultura) return;
  try {
    const list = await wizList('/api/culturas/');
    const hit = list.find((c) => wizNorm(c.nome).includes(wizNorm(q.especie.cultura)));
    if (!hit) return;
    if (typeof window.safeShowCulturaDetail === 'function')
      window.safeShowCulturaDetail(hit.id, hit.nome, 'aquatica');
    else if (typeof window.showCulturaDetail === 'function')
      window.showCulturaDetail(hit.id, hit.nome, 'aquatica');
  } catch {}
}
function wizAquaStart() {
  wizAqua = {
    step: 'especie',
    especie: null,
    sistema: null,
    ambiente: null,
    qtd: null,
    biomassa: null,
    data: null,
    lote: null,
  };
  return 'Vamos cadastrar um lote aquícola! 🐟\n[ ] Espécie\n[ ] Sistema\n[ ] Ambiente\n[ ] Quantidade\n[ ] Povoamento\n\nQual a espécie? (tilápia, tambaqui, carpa, camarão…)';
}
async function wizAquaStep(texto) {
  const q = wizAqua;
  const t = (texto || '').trim();
  if (wizCancelar(t)) {
    wizAqua = null;
    return 'Fluxo cancelado. Quando quiser, é só dizer "cadastrar peixe".';
  }
  const _g = await wizGuardas(WIZ_META.aqua, 'aqua', texto);
  if (_g) return _g;
  if (q.step === 'especie') {
    const e = wizEspecieAqua(t);
    if (!e)
      return 'Não identifiquei. Opções: tilápia, tambaqui, carpa, pintado, pirarucu, truta, camarão. Qual a espécie?';
    q.especie = e;
    q.step = 'sistema';
    wizNavegarAqua(q);
    const nav = e.cultura ? ' — abri a guia dela' : '';
    return `${wizAquaChecklist(q)}\n\n${
      e.label
    }${nav}. Qual o sistema? (viveiro escavado, tanque-rede, tanque elevado, aquaponia, bioflocos — Enter = viveiro)`;
  }
  if (q.step === 'sistema') {
    if (!t) {
      q.sistema = 'VIVEIRO_ESCAVADO';
    } else {
      const sis = wizSistemaAqua(t);
      if (!sis)
        return 'Não entendi — viveiro escavado, tanque-rede, tanque elevado, aquaponia ou bioflocos? (Enter = viveiro)';
      q.sistema = sis;
    }
    q.step = 'ambiente';
    return `${wizAquaChecklist(q)}\n\nQual o tanque/viveiro? (nome do ambiente — Enter = pular)`;
  }
  if (q.step === 'ambiente') {
    const n = wizNorm(t);
    q.ambiente = !t || /pular/.test(n) ? null : t;
    q.step = 'qtd';
    return `${wizAquaChecklist(q)}\n\nQuantidade de alevinos/peixes?`;
  }
  if (q.step === 'qtd') {
    const num = wizParseNum(t);
    if (!num || num <= 0) return 'Preciso da quantidade (ex: 1000 — pode escrever "mil"). Quantos?';
    if (num > 10000000) {
      const nq = Math.round(num);
      return wizArmarConfirm(
        WIZ_META.aqua,
        `⚠️ ${nq} peixes é um lote gigante — confirma que é isso mesmo? (sim/não)`,
        async () => {
          q.qtd = nq;
          q.step = 'biomassa';
          return `${wizAquaChecklist(q)}\n\nPeso médio por peixe em gramas? (Enter = pular)`;
        },
        'Ok, quantos peixes?'
      );
    }
    q.qtd = Math.round(num);
    q.step = 'biomassa';
    return `${wizAquaChecklist(q)}\n\nPeso médio por peixe em gramas? (Enter = pular)`;
  }
  if (q.step === 'biomassa') {
    const num = wizParseNum(t);
    if (num && num > 50000) {
      return wizArmarConfirm(
        WIZ_META.aqua,
        `⚠️ ${num} g por peixe é bem alto — confirma? (sim/não)`,
        async () => {
          q.biomassa = num;
          q.step = 'data';
          return `${wizAquaChecklist(q)}\n\nData do povoamento? (dd/mm/aaaa — ou diga "hoje")`;
        },
        'Ok, qual o peso médio em gramas? (ou Enter para pular)'
      );
    }
    q.biomassa = num && num > 0 ? num : null;
    q.step = 'data';
    return `${wizAquaChecklist(q)}\n\nData do povoamento? (dd/mm/aaaa — ou diga "hoje")`;
  }
  if (q.step === 'data') {
    const d = wizParseDatas(t);
    // A data do povoamento NAO e' hoje quando o produtor nao sabe. Este
    // passo grava e faz POST — um `wizHoje()` aqui Fabrica uma data de
    // povoamento, e a populacao errado propaga-se a biomassa, a racao e a
    // despesca do lote. A correccao e PERGUNTAR (como o passo `admissao`
    // faz), e nao inventar outro valor.
    if (!d.length) {
      return `${wizAquaChecklist(q)}\n\nNao encontrei a data. Em que dia foi o povoamento? (dd/mm/aaaa ou "pular" para deixar em branco)`;
    }
    q.data = d[0];
    const propId = await wizPropAnimal(null);
    try {
      const payload = {
        propriedade: propId,
        especie: q.especie.code,
        sistema: q.sistema,
        quantidade: q.qtd,
        data_povoamento: q.data,
      };
      if (q.ambiente) payload.ambiente = q.ambiente;
      if (q.biomassa) payload.biomassa_media = q.biomassa;
      const created = await apiFetch('/api/lotes-aquaticos/', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      q.lote = created;
      q.step = 'ramo';
      return `${wizAquaChecklist(q)}\n\nPronto, lote criado! ✅ ${
        q.qtd
      } ${q.especie.label.toLowerCase()} (povoamento ${wizFmtData(
        q.data
      )}).\nQuer registrar uma despesca ou fechar?`;
    } catch (e) {
      return `Não consegui criar o lote: ${e.message}. Quantos peixes?`;
    }
  }
  if (q.step === 'ramo') {
    const n = wizNorm(t);
    if (wizAnimalTrigger(t)) {
      wizAqua = null;
      return wizAnimalStart();
    }
    if (wizTrigger(t)) {
      wizAqua = null;
      return wizSafraStart(typeof t !== 'undefined' ? t : lastUser);
    }
    if (typeof wizTalhaoTrigger === 'function' && wizTalhaoTrigger(t)) {
      wizAqua = null;
      return wizTalhaoStart(t);
    }
    if (typeof wizFuncRemTrigger === 'function' && wizFuncRemTrigger(t)) {
      wizAqua = null;
      return wizFuncRemStart(t);
    }
    if (typeof wizFuncTrigger === 'function' && wizFuncTrigger(t)) {
      wizAqua = null;
      return wizFuncStart(t);
    }
    if (typeof wizTarefaTrigger === 'function' && wizTarefaTrigger(t)) {
      wizAqua = null;
      return wizTarefaStart(t);
    }
    if (wizSim(t)) return 'Diga um dos dois: despesca ou fechar?';
    if (/despesca|colheita|retirada|venda/.test(n)) {
      q.step = 'desp_data';
      return 'Vamos registrar a despesca. Qual a data? (dd/mm/aaaa — ou diga "hoje")';
    }
    if (/fechar|pronto|chega|nao|depois|por enquanto/.test(n)) {
      wizAqua = null;
      return 'Fechado! ✅ Lote salvo. Se precisar: despesca ou novo lote — é só chamar.';
    }
    return 'Quer registrar uma despesca ou fechar?';
  }
  if (q.step === 'desp_data') {
    const d = wizParseDatas(t);
    // Uma despesca sem data legivel NAO e' uma despesca de hoje: e' uma
    // despesca sem data. Perguntar e' mais honesto que assumir, e o produtor
    // sabe a data — a maquina nao.
    if (!d.length) {
      return `${wizAquaChecklist(q)}\n\nNao encontrei a data da despesca. Em que dia foi? (dd/mm/aaaa ou "pular")`;
    }
    const dataIso = d[0];
    if (dataIso > wizHoje()) {
      return wizArmarConfirm(
        WIZ_META.aqua,
        `⚠️ ${wizFmtData(dataIso)} ainda nem chegou — é uma despesca prevista? (sim/não)`,
        async () => {
          q.despData = dataIso;
          q.step = 'desp_kg';
          return 'Quantos kg foram despescados?';
        },
        'Ok, qual a data da despesca? (dd/mm/aaaa — ou diga "hoje")'
      );
    }
    q.despData = dataIso;
    q.step = 'desp_kg';
    return 'Quantos kg foram despescados?';
  }
  if (q.step === 'desp_kg') {
    const num = wizParseNum(t);
    if (!num || num <= 0) return 'Quantos kg? (ex: 250)';
    if (num > 100000) {
      return wizArmarConfirm(
        WIZ_META.aqua,
        `⚠️ ${num} kg é uma despesca gigante — confirma? (sim/não)`,
        async () => {
          q.despKg = num;
          q.step = 'desp_valor';
          return `Anotado: ${num} kg. Valor estimado em R$? (Enter = pular)`;
        },
        'Ok, quantos kg?'
      );
    }
    q.despKg = num;
    q.step = 'desp_valor';
    return `Anotado: ${num} kg. Valor estimado em R$? (Enter = pular)`;
  }
  if (q.step === 'desp_valor') {
    const num = wizParseNum(t);
    if (num && num > 100000000) {
      return wizArmarConfirm(
        WIZ_META.aqua,
        `⚠️ R$ ${num} é um valor bem alto — confirma? (sim/não)`,
        async () => {
          const payload = {
            lote: q.lote.id,
            data: q.despData,
            quantidade_kg: q.despKg,
            valor_estimado: num,
          };
          await apiFetch('/api/despescas/', { method: 'POST', body: JSON.stringify(payload) });
          q.step = 'pos';
          return `Despesca registrada! ✅ ${q.despKg} kg.\nO que mais? (outra despesca, novo lote, ou fechar)`;
        },
        'Ok, qual o valor em R$? (ou Enter para pular)'
      );
    }
    try {
      const payload = { lote: q.lote.id, data: q.despData, quantidade_kg: q.despKg };
      if (num && num > 0) payload.valor_estimado = num;
      await apiFetch('/api/despescas/', { method: 'POST', body: JSON.stringify(payload) });
      q.step = 'pos';
      return `Despesca registrada! ✅ ${q.despKg} kg.\nO que mais? (outra despesca, novo lote, ou fechar)`;
    } catch (e) {
      q.step = 'pos';
      return `Não consegui registrar: ${e.message}. O que mais?`;
    }
  }
  if (q.step === 'pos') {
    const n = wizNorm(t);
    if (wizAnimalTrigger(t)) {
      wizAqua = null;
      return wizAnimalStart();
    }
    if (wizTrigger(t)) {
      wizAqua = null;
      return wizSafraStart(typeof t !== 'undefined' ? t : lastUser);
    }
    if (typeof wizTalhaoTrigger === 'function' && wizTalhaoTrigger(t)) {
      wizAqua = null;
      return wizTalhaoStart(t);
    }
    if (typeof wizFuncRemTrigger === 'function' && wizFuncRemTrigger(t)) {
      wizAqua = null;
      return wizFuncRemStart(t);
    }
    if (typeof wizFuncTrigger === 'function' && wizFuncTrigger(t)) {
      wizAqua = null;
      return wizFuncStart(t);
    }
    if (typeof wizTarefaTrigger === 'function' && wizTarefaTrigger(t)) {
      wizAqua = null;
      return wizTarefaStart(t);
    }
    if (/despesca/.test(n)) {
      q.step = 'desp_data';
      return 'Qual a data da despesca? (dd/mm/aaaa — ou diga "hoje")';
    }
    if (/novo lote|outro lote|cadastrar/.test(n)) return wizAquaStart();
    wizAqua = null;
    return 'Fechado! ✅ Se precisar, é só chamar: lote ou despesca.';
  }
  wizAqua = null;
  return 'Vamos recomeçar: diga "cadastrar peixe".';
}
/* ══ datas relativas: amanhã, dia N, próxima sexta, semana que vem ══ */
const WIZ_DIAS_SEMANA = {
  domingo: 0,
  segunda: 1,
  terca: 2,
  quarta: 3,
  quinta: 4,
  sexta: 5,
  sabado: 6,
};
function wizDataRelativa(t) {
  const d = wizParseDatas(t);
  if (d.length) return d[0];
  const n = wizNorm(String(t || ''));
  const H = wizHoje();
  if (/\bhoje\b/.test(n)) return H;
  if (/depois de amanha/.test(n)) return wizSomarDias(H, 2);
  if (/\bamanha\b/.test(n)) return wizSomarDias(H, 1);
  if (/semana que vem|proxima semana/.test(n)) return wizSomarDias(H, 7);
  for (const [nome, dow] of Object.entries(WIZ_DIAS_SEMANA)) {
    if (new RegExp('\\b' + nome + '\\b').test(n)) {
      const [a, m, dd] = H.split('-').map(Number);
      const hoje = new Date(a, m - 1, dd).getDay();
      let delta = (dow - hoje + 7) % 7;
      if (/que vem|proxima/.test(n) && delta === 0) delta = 7;
      return wizSomarDias(H, delta);
    }
  }
  return null;
}
/* ═══════════════════════════════════════════════════════════
   WIZARD TALHÃO — nome → área → cultura? → cria; + vínculo
   cultura↔talhão ("adiciona milho no talhão norte").
   ═══════════════════════════════════════════════════════════ */
let wizTalhaoF = null;
let wizVinc = null;
function wizTalhaoTrigger(t) {
  // Desativado: Backend (sandbox.py) resolve o talhão agora
  return false;
}
function wizVincTrigger(t) {
  if (wizEhInterrogacao(t)) return false;
  const n = wizNorm(t);
  if (!/cultura/.test(n) || !/talh/.test(n)) return false;
  return /adicion|associa|liga|vincula|coloca|planta|muda|troca/.test(n);
}
function wizTalhaoPrefill(t) {
  const out = { nome: null, area: null };
  const m = String(t || '').match(/chamad[oa]\s+([A-Za-zÀ-ú0-9 ]+?)(?:\s+com|\s+\d|,|$)/i);
  if (m) out.nome = m[1].trim();
  if (/hectare|\bha\b/i.test(String(t || ''))) {
    const v = wizParseNum(t);
    if (v && v > 0) out.area = v;
  }
  return out;
}
function wizTalhaoChecklist(f) {
  const L = [];
  L.push((f.nome ? '[✓]' : '[ ]') + ' Nome' + (f.nome ? ': ' + f.nome : ''));
  L.push((f.area ? '[✓]' : '[ ]') + ' Área' + (f.area ? ': ' + f.area + ' ha' : ''));
  L.push(
    (f.cultura !== undefined && f.cultura !== null ? '[✓]' : '[ ]') +
      ' Cultura' +
      (f.cultura ? ': ' + f.cultura.nome : '')
  );
  return L.join('\n');
}
function wizTalhaoStart(texto) {
  wizTalhaoF = { step: 'nome', nome: null, area: null, cultura: null };
  const pre = wizTalhaoPrefill(texto || '');
  if (pre.nome) wizTalhaoF.nome = pre.nome;
  if (pre.area) wizTalhaoF.area = pre.area;
  if (pre.nome && pre.area) {
    wizTalhaoF.step = 'cultura';
    return `Beleza, ${pre.nome} com ${pre.area} ha! 🗺️\n${wizTalhaoChecklist(
      wizTalhaoF
    )}\n\nAlguma cultura nele? (nome — ou Enter para pular)`;
  }
  if (pre.nome) {
    wizTalhaoF.step = 'area';
    return `${wizTalhaoChecklist(wizTalhaoF)}\n\nQual a área em ha?`;
  }
  return 'Vamos cadastrar um talhão! 🗺️\n[ ] Nome\n[ ] Área\n[ ] Cultura\n\nQual o nome do talhão?';
}
async function wizTalhaoStep(texto) {
  const f = wizTalhaoF;
  const t = (texto || '').trim();
  if (wizCancelar(t)) {
    wizTalhaoF = null;
    return 'Fluxo cancelado. Quando quiser, é só dizer "cadastrar talhão".';
  }
  const _g = await wizGuardas(WIZ_META.talhao, 'talhao', texto);
  if (_g) return _g;
  if (f.step === 'nome') {
    if (!t) return 'Qual o nome do talhão? (ex: Sul, Baixada)';
    if (wizSim(t) || wizNao(t)) return 'Preciso do nome do talhão (ex: Sul). Qual é?';
    // "como voces chamam esse talhao?" e' a nossa pergunta, nao a resposta.
    // Sem esta guarda o talhao grava-se com o texto da pergunta e o POST vai
    // com ele — e o nome errado propaga-se a safras, aplicacoes e custo/ha.
    if (wizNaoEhValor(t)) return 'Qual o nome do talhão? (ex: Sul, Baixada)';
    f.nome = t;
    const pre = wizTalhaoPrefill(texto);
    if (pre.area) f.area = pre.area;
    f.step = f.area ? 'cultura' : 'area';
    if (f.area)
      return `${wizTalhaoChecklist(f)}\n\nAlguma cultura nele? (nome — ou Enter para pular)`;
    return `${wizTalhaoChecklist(f)}\n\nQual a área em ha?`;
  }
  if (f.step === 'area') {
    const num = wizParseNum(t);
    if (!num || num <= 0) return 'Qual a área do talhão em ha? (ex: 50)';
    if (num > 100000) {
      return wizArmarConfirm(
        WIZ_META.talhao,
        `⚠️ ${num} ha é uma área bem grande — confirma? (sim/não)`,
        async () => {
          f.area = num;
          f.step = 'cultura';
          return `${wizTalhaoChecklist(f)}\n\nAlguma cultura nele? (nome — ou Enter para pular)`;
        },
        'Ok, qual a área correta em ha?'
      );
    }
    f.area = num;
    f.step = 'cultura';
    return `${wizTalhaoChecklist(f)}\n\nAlguma cultura nele? (nome — ou Enter para pular)`;
  }
  if (f.step === 'cultura') {
    const n = wizNorm(t);
    if (!t || /pular|sem|nenhuma|nao/.test(n)) {
      f.cultura = null;
    } else {
      const list = await wizList('/api/culturas/');
      const r = wizEscolher(list, t);
      // `_cultNota` é uma NOTA sobre o que ficou por preencher, não uma
      // pergunta. Por isso não repete a frase que a pessoa escreveu: o
      // que interessa avisar é que o talhão vai ficar sem cultura.
      if (!r.tal) {
        f.cultura = null;
        f._cultNota = wizEhPergunta(t)
          ? ' (perguntou qual cultura — deixei sem cultura, pode dizer agora)'
          : ` (não achei${wizEcoCurto(t)} — deixei sem cultura)`;
      } else f.cultura = r.tal;
    }
    const criar = async () => {
      try {
        const payload = {
          propriedade: await wizPropAnimal(null),
          nome: f.nome,
          area_hectare: f.area,
        };
        if (f.cultura) payload.cultura_atual = f.cultura.id;
        const created = await apiFetch('/api/talhoes/', {
          method: 'POST',
          body: JSON.stringify(payload),
        });
        f.talhaoId = created.id;
        f.step = 'pos';
        return `${wizTalhaoChecklist(f)}\n\nTalhão "${f.nome}" criado! ✅ (${f.area} ha${
          f._cultNota || ''
        })\nO que mais? (vincular cultura, novo talhão, ou fechar)`;
      } catch (e) {
        return `Não consegui criar: ${e.message}. Qual a área em ha?`;
      }
    };
    try {
      const todos = await wizList('/api/talhoes/');
      const dup = todos.find((x) => wizNorm(x.nome) === wizNorm(f.nome));
      if (dup) {
        return wizArmarConfirm(
          WIZ_META.talhao,
          `⚠️ Já existe talhão "${f.nome}". Criar outro mesmo assim? (sim/não)`,
          criar,
          'Ok — qual o nome do talhão? (diga "voltar" pra corrigir)'
        );
      }
    } catch {}
    return await criar();
  }
  if (f.step === 'pos') {
    const xp = wizTrocaPos(t, () => {
      wizTalhaoF = null;
    });
    if (xp) return xp;
    const n = wizNorm(t);
    if (/vincula|cultura/.test(n)) {
      f.step = 'vinc';
      return 'Qual cultura vincular ao talhão? (nome)';
    }
    if (/novo|outro|cadastrar/.test(n)) return wizTalhaoStart();
    wizTalhaoF = null;
    return 'Fechado! ✅ Se precisar: talhão, cultura ou safra — é só chamar.';
  }
  if (f.step === 'vinc') {
    const hit = (await wizBuscarCultura(t))[0] || null;
    if (!hit) return `Não achei cultura "${t}". Qual cultura vincular?`;
    try {
      await apiFetch(`/api/talhoes/${f.talhaoId}/`, {
        method: 'PATCH',
        body: JSON.stringify({ cultura_atual: hit.id }),
      });
    } catch {}
    f.step = 'pos';
    return `Pronto! ✅ ${hit.nome} vinculado ao talhão. O que mais?`;
  }
  wizTalhaoF = null;
  return 'Vamos recomeçar: diga "cadastrar talhão".';
}
function wizVincStart(texto) {
  wizVinc = {
    step: 'cultura',
    cultura: null,
    talhao: null,
    _textoInicial: texto || '',
    _tentouPre: false,
  };
  return 'Vamos ligar cultura e talhão! 🔗\nQual a cultura?';
}
async function wizVincStep(texto) {
  const v = wizVinc;
  const t = (texto || '').trim();
  if (wizCancelar(t)) {
    wizVinc = null;
    return 'Fluxo cancelado.';
  }
  const _g = await wizGuardas(WIZ_META.vinc, 'vinc', texto);
  if (_g) return _g;
  if (v.step === 'cultura') {
    if (!v._tentouPre && v._textoInicial) {
      v._tentouPre = true;
      const pre = await wizVincPrefill(v._textoInicial);
      if (pre.cultura) {
        v.cultura = pre.cultura;
        if (pre.talhao) {
          v.talhao = pre.talhao;
          v.step = 'conf';
          return `Entendi: ${pre.cultura.nome} no talhão ${pre.talhao.nome}. Confirmo? (sim/não)`;
        }
        v.step = 'talhao';
        return `Cultura: ${pre.cultura.nome}. Em qual talhão?`;
      }
    }
    const hitsV = await wizBuscarCultura(t);
    const hit = hitsV[0] || null;
    if (!hit) {
      const list = await wizList('/api/culturas/');
      const porPergunta = wizEhPergunta(t)
        ? wizComPergunta('essa cultura', list, 'Qual a cultura?')
        : null;
      return porPergunta || wizSemAcerto('essa cultura', list, t);
    }
    v.cultura = hit;
    v.step = 'talhao';
    return `Cultura: ${hit.nome}. Em qual talhão?`;
  }
  if (v.step === 'talhao') {
    const list = await wizList('/api/talhoes/');
    const r = wizEscolher(list, t);
    if (r.alternativa.length) {
      return `Achei ${r.alternativa.length}: ${wizNomes(r.alternativa, 5).join(', ')}. Qual deles?`;
    }
    if (!r.tal) {
      const porPergunta = wizEhPergunta(t)
        ? wizComPergunta('esse talhão', list, 'Em qual talhão?')
        : null;
      if (porPergunta) return porPergunta;
      if (v._talhaoRetryCount === undefined) v._talhaoRetryCount = 0;
      v._talhaoRetryCount++;
      if (v._talhaoRetryCount >= 2) {
        v.talhao = null;
        v.step = 'conf';
        return `Sem talhão por enquanto — tudo bem.\nPlantar ${v.cultura.nome} sem talhão vinculado? (sim/não)`;
      }
      return wizSemAcerto('esse talhão', list, t);
    }
    const hit = r.tal;
    v.talhao = hit;
    v.step = 'conf';
    return `Plantar ${v.cultura.nome} no talhão ${hit.nome}? (sim/não)`;
  }
  if (v.step === 'conf') {
    if (wizSim(t)) {
      try {
        await apiFetch(`/api/talhoes/${v.talhao.id}/`, {
          method: 'PATCH',
          body: JSON.stringify({ cultura_atual: v.cultura.id }),
        });
        wizVinc = null;
        return `Pronto! ✅ ${v.cultura.nome} agora está no ${v.talhao.nome}.`;
      } catch (e) {
        wizVinc = null;
        return `Não consegui vincular: ${e.message}.`;
      }
    }
    if (wizNao(t)) {
      wizVinc = null;
      return 'Fechado, sem vincular. 👍';
    }
    return `Plantar ${v.cultura.nome} no talhão ${v.talhao.nome}? (sim/não)`;
  }
  wizVinc = null;
  return 'Vamos recomeçar: diga "adicionar cultura no talhão".';
}
async function wizVincPrefill(t) {
  try {
    const tals = await wizList('/api/talhoes/');
    const c = await wizPrefillCultura(t);
    const th = wizEscolher(tals, t).tal;
    return { cultura: c || null, talhao: th || null };
  } catch {
    return { cultura: null, talhao: null };
  }
}
/* ═══════════════════════════════════════════════════════════
   WIZARD FUNCIONÁRIO — nome → cargo → salário → admissão →
   telefone? → cria; + REMOVER (busca → confirma → desativa).
   ═══════════════════════════════════════════════════════════ */
let wizFunc = null;
let wizFuncRem = null;
const WIZ_CARGOS = [
  { code: 'GERENTE', keys: ['gerente'] },
  { code: 'CAPATAZ', keys: ['capataz', 'encarregado'] },
  { code: 'ADMIN', keys: ['admin'] },
  { code: 'TRATORISTA', keys: ['tratorista'] },
  { code: 'OPERADOR_COLHEITADEIRA', keys: ['colheitadeira'] },
  { code: 'OPERADOR_PULVERIZADOR', keys: ['pulverizador'] },
  { code: 'OPERADOR_PLANTADEIRA', keys: ['plantadeira'] },
  { code: 'OPERADOR_ROCADEIRA', keys: ['rocadeira'] },
  { code: 'OPERADOR_IRRIGACAO', keys: ['irrigac'] },
  { code: 'AUX_CAMPO', keys: ['auxiliar de campo'] },
  { code: 'DIARISTA', keys: ['diarista'] },
  { code: 'RURICOLA', keys: ['ruricola'] },
  { code: 'VAQUEIRO', keys: ['vaqueiro'] },
  { code: 'PEAO', keys: ['peao'] },
  { code: 'MOTORISTA', keys: ['motorista'] },
  { code: 'MECANICO_AGRICOLA', keys: ['mecanico'] },
  { code: 'CASEIRO', keys: ['caseiro'] },
  { code: 'COZINHEIRO_RURAL', keys: ['cozinheir'] },
  { code: 'VIGIA', keys: ['vigia', 'seguranca'] },
  { code: 'TECNICO', keys: ['tecnico agricola', 'tecnica agricola'] },
  { code: 'ENGENHEIRO', keys: ['engenheiro', 'agronomo'] },
  { code: 'VETERINARIO', keys: ['veterinario'] },
  { code: 'ORDENHADOR', keys: ['ordenhador'] },
  { code: 'SOLDADOR', keys: ['soldador'] },
  { code: 'ELETRICISTA_RURAL', keys: ['eletricista'] },
  { code: 'SERVICO', keys: ['servicos gerais'] },
];
function wizFuncTrigger(t) {
  if (wizEhInterrogacao(t)) return false;
  const n = wizNorm(t);
  if (/remove|exclu|delet|demit|deslig|lista|quais|quem|mostra|quantos/.test(n)) return false;
  if (
    !/(usuario|funcionario|operador|colaborador|equipe|contrata|membro|ajudante|tecnico|admin|cargo|funcao)/.test(
      n
    )
  )
    return false;
  return /cadastr|cria\w*|crie|nov[oa]|adicion|registr|comec|inici|contrata/.test(n);
}
function wizFuncRemTrigger(t) {
  if (wizEhInterrogacao(t)) return false;
  const n = wizNorm(t);
  if (!/(remove|remover|exclu|delet|demit|deslig|tira)/.test(n)) return false;
  return /(equipe|funcionario|usuario|operador|colaborador)/.test(n);
}
function wizFuncNome(t) {
  let m = String(t || '').match(/nome\s+(?:é|e)?\s*([A-Za-zÀ-ú ]+?)(?:\s+como|,|$)/i);
  if (m) return m[1].trim();
  m = String(t || '').match(
    /(?:cadastra|adiciona|crie|criar)\s+(?:o\s+|a\s+|um\s+|uma\s+)?([A-Za-zÀ-ú ]+?)\s+como\s+/i
  );
  if (m) return m[1].trim();
  return null;
}
function wizFuncCargos(t) {
  const n = wizNorm(t);
  return WIZ_CARGOS.filter((c) => c.keys.some((k) => n.includes(k)));
}
function wizFuncChecklist(f) {
  const L = [];
  L.push((f.nome ? '[✓]' : '[ ]') + ' Nome' + (f.nome ? ': ' + f.nome : ''));
  L.push((f.cargo ? '[✓]' : '[ ]') + ' Cargo' + (f.cargo ? ': ' + f.cargo : ''));
  L.push(
    (f.salario !== undefined && f.salario !== null ? '[✓]' : '[ ]') +
      ' Salário' +
      (f.salario !== undefined && f.salario !== null ? ': R$ ' + f.salario : '')
  );
  L.push(
    (f.admissao ? '[✓]' : '[ ]') + ' Admissão' + (f.admissao ? ': ' + wizFmtData(f.admissao) : '')
  );
  return L.join('\n');
}
function wizFuncStart(texto) {
  wizFunc = {
    step: 'nome',
    nome: wizFuncNome(texto || ''),
    cargo: null,
    salario: null,
    admissao: null,
    fone: null,
  };
  const hits = wizFuncCargos(texto || '');
  if (hits.length === 1) wizFunc.cargo = hits[0].code;
  if (wizFunc.nome && wizFunc.cargo) {
    wizFunc.step = 'salario';
    return `Beleza, ${wizFunc.nome} (${wizFunc.cargo})! 👷\n${wizFuncChecklist(
      wizFunc
    )}\n\nQual o salário em R$? (ou "a combinar")`;
  }
  if (wizFunc.nome) {
    wizFunc.step = 'cargo';
    return `${wizFuncChecklist(wizFunc)}\n\nQual a função? (ex: tratorista, diarista, vaqueiro)`;
  }
  return 'Vamos cadastrar gente! 👷\n[ ] Nome\n[ ] Cargo\n[ ] Salário\n[ ] Admissão\n\nQual o nome?';
}
async function wizFuncStep(texto) {
  const f = wizFunc;
  const t = (texto || '').trim();
  if (wizCancelar(t)) {
    wizFunc = null;
    return 'Fluxo cancelado.';
  }
  const _g = await wizGuardas(WIZ_META.func, 'func', texto);
  if (_g) return _g;
  if (f.step === 'nome') {
    if (!t) return 'Qual o nome?';
    if (wizSim(t) || wizNao(t)) return 'Preciso do nome da pessoa. Qual é?';
    // A pergunta do sistema nao e' o nome da pessoa. Sem a guarda, o
    // funcionario fica com "qual o nome?" no campo `nome` — e um cadastro
    // de vaqueiro chamado "qual o nome?" passa a ser um registo real.
    if (wizNaoEhValor(t)) return 'Qual o nome da pessoa? (ex: João, Maria)';
    f.nome = t;
    f.step = 'cargo';
    return `${wizFuncChecklist(f)}\n\nQual a função? (ex: tratorista, diarista, vaqueiro)`;
  }
  if (f.step === 'cargo') {
    const hits = wizFuncCargos(t);
    if (!hits.length)
      return 'Não identifiquei a função. Opções: gerente, tratorista, diarista, vaqueiro, motorista, mecânico, caseiro, técnico agrícola... Qual?';
    if (hits.length > 1) {
      return `"Operador" é genérico — operador de quê? (${hits
        .slice(0, 4)
        .map((h) => h.code.toLowerCase().replace(/_/g, ' '))
        .join(', ')})`;
    }
    f.cargo = hits[0].code;
    f.step = 'salario';
    return `${wizFuncChecklist(f)}\n\nQual o salário em R$? (ou "a combinar")`;
  }
  if (f.step === 'salario') {
    const n = wizNorm(t);
    if (!t || /combinar|pular|nao sei/.test(n)) {
      f.salario = 0;
      f._salNota = ' (a combinar — ajuste no cadastro)';
    } else {
      const num = wizParseNum(t);
      if (num == null || num < 0) return 'Qual o salário em R$? (só o número — ou "a combinar")';
      f.salario = num;
    }
    f.step = 'admissao';
    // O "Enter = hoje" desapareceu. Prometer que o vazio vira uma data e'
    // outra forma de fabricar a mesma medicao que o `wizHoje()` fazia, e desta
    // vez DIZIDA ao produtor — o que e' pior, porque o produtor concorda com
    // algo que o sistema inventou. Ver o comentario em `step === 'admissao'`.
    return `${wizFuncChecklist(f)}\n\nData de admissão? (dd/mm/aaaa)`;
  }
  if (f.step === 'admissao') {
    const d = wizParseDatas(t);
    // MEDIDO, 2026-10-04 (achado do agente 10, confirmado): antes isto era
    //     f.admissao = d.length ? d[0] : wizHoje();
    // e `wizHoje()` fabrica uma DATA. A pergunta "quando ele entrou?" devolvia
    // a data de hoje, sem dizer nada.
    //
    // Isto viola DUAS doutrinas do projecto ao mesmo tempo:
    //   1. a separacao raciocino/acao do manifesto — "uma IA nao altera o estado
    //      da fazenda; ela compila uma transacao segura que o sistema valida e
    //      o produtor aprova". Aqui nao ha transacao para aprovar: ha um valor
    //      fabricado num campo que vai ser gravado.
    //   2. `app/validators.py:40-41` — "o sistema nunca promove uma afirmacao a
    //      medicao". `wizHoje()` fabrica uma medicao.
    //
    // E e' o mais perigoso porque NAO PARECE ERRO. Um erro visivel corrige-se;
    // uma data de admissao plausivel entra no cadastro e ninguem a questiona
    // durante meses. O mesmo se passa com o "Enter = hoje" do convite acima.
    //
    // A correccaoi NAO e inventar outra coisa: e PERGUNTAR. Sem `confirm: true`
    // a sandbox devolve `needs_confirm` e o produtor ve a pergunta — que e o
    // que `h_remarcar_tarefa` ja faz e esta a funcionar.
    if (!d.length) {
      // A opcao (b) — gravar ausente e marcar `sem_dado` — NAO e' possivel
      // aqui: `data_admissao` e' `NOT NULL` (app/models/equipe.py:296), logo
      // "pular" nao deixaria o campo em branco, o POST voltaria com 400, e
      // `Funcionario` nem sequer tem coluna para a origem. Por isso a
      // correcao e' (a): PERGUNTAR, e dizer que o campo e' obrigatorio — que
      // e' a verdade. O que nao pode voltar a acontecer e' o `wizHoje()`.
      f.step = 'admissao';
      return `${wizFuncChecklist(f)}\n\nNao encontrei a data. Em que dia ele entrou? (dd/mm/aaaa — este campo e' obrigatorio no cadastro)`;
    }
    f.admissao = d[0];
    f.step = 'fone';
    return `${wizFuncChecklist(f)}\n\nTelefone/WhatsApp? (Enter = pular)`;
  }
  if (f.step === 'fone') {
    const n = wizNorm(t);
    if (t && !/pular|sem|nao/.test(n)) {
      const dig = t.replace(/\D/g, '');
      if (dig.length > 20)
        return 'Esse número ficou longo demais — me passa só DDD + número (ex: 66999990000). Qual o telefone? (ou Enter para pular)';
      f.fone = dig || null;
      if (!dig && t.length > 30)
        return 'Não entendi o telefone — me passa só DDD + número (ou Enter para pular).';
      if (!dig) f.fone = null;
    } else f.fone = null;
    try {
      const payload = {
        propriedade: await wizPropAnimal(null),
        nome: f.nome,
        cargo: f.cargo,
        salario: f.salario,
        data_admissao: f.admissao,
      };
      if (f.fone) payload.telefone = f.fone;
      const created = await apiFetch('/api/funcionarios/', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      wizFunc = null;
      return `Pronto! ✅ ${f.nome} (${f.cargo}) cadastrado${
        f._salNota || ''
      }.\nSe precisar: outro funcionário, equipe, ou outra coisa — é só chamar.`;
    } catch (e) {
      return `Não consegui cadastrar: ${e.message}. Qual o telefone? (ou Enter para pular)`;
    }
  }
  wizFunc = null;
  return 'Vamos recomeçar: diga "cadastrar funcionário".';
}
function wizFuncRemStart(texto) {
  wizFuncRem = { step: 'alvo', nome: null, alvo: null };
  const resto = String(texto || '')
    .replace(/remover|remove|exclu\w*|delet\w*|demit\w*|deslig\w*|tira\w*/gi, ' ')
    .replace(/da equipe|do time|equipe|funcionario|usuario|operador|colaborador|por favor/gi, ' ')
    .replace(/^(o|a|os|as|um|uma|de|do|da)\s+/gi, '')
    .replace(/\s+/g, ' ')
    .trim();
  if (resto.length > 2) wizFuncRem.nome = resto;
  return 'Quem sai da equipe? (nome da pessoa)';
}
async function wizFuncRemStep(texto) {
  const r = wizFuncRem;
  const t = (texto || '').trim();
  if (wizCancelar(t)) {
    wizFuncRem = null;
    return 'Fluxo cancelado, ninguém foi removido. 👍';
  }
  const _g = await wizGuardas(WIZ_META.funcrem, 'funcrem', texto);
  if (_g) return _g;
  if (r.step === 'alvo') {
    const busca = t || r.nome || '';
    if (!busca) return 'Quem sai da equipe? (nome da pessoa)';
    const list = await wizList('/api/funcionarios/');
    const achado = wizEscolher(list, busca);
    if (achado.alternativa.length) {
      return `Achei ${achado.alternativa.length}: ${wizNomes(achado.alternativa, 5).join(
        ', '
      )}. Quem sai?`;
    }
    if (!achado.tal) {
      const porPergunta = wizEhPergunta(busca)
        ? wizComPergunta('ninguém com esse nome', list, 'Quem sai da equipe?')
        : null;
      return porPergunta || wizSemAcerto('ninguém com esse nome', list, busca);
    }
    r.alvo = achado.tal;
    r.step = 'conf';
    return `Remover ${r.alvo.nome} (${
      r.alvo.cargo_display || r.alvo.cargo
    }) da equipe? Isso desativa o cadastro (dá pra reverter). (sim/não)`;
  }
  if (r.step === 'conf') {
    if (wizSim(t)) {
      try {
        await apiFetch(`/api/funcionarios/${r.alvo.id}/`, {
          method: 'PATCH',
          body: JSON.stringify({ ativo: false }),
        });
        wizFuncRem = null;
        return `Pronto — ${r.alvo.nome} desativado. ✅ (O cadastro continua no sistema, só inativo.)`;
      } catch (e) {
        wizFuncRem = null;
        return `Não consegui remover: ${e.message}.`;
      }
    }
    if (wizNao(t)) {
      wizFuncRem = null;
      return 'Fechado, ninguém foi removido. 👍';
    }
    return `Remover ${r.alvo.nome} da equipe? (sim/não)`;
  }
  wizFuncRem = null;
  return 'Vamos recomeçar: diga "remover funcionário".';
}
/* ═══════════════════════════════════════════════════════════
   WIZARD TAREFA — o quê → quando (datas relativas!) → pra quem?
   → cria; + CANCELAR (lista → escolhe → confirma → exclui).
   ═══════════════════════════════════════════════════════════ */
let wizTarefa = null;
let wizTarCancel = null;
function wizTarefaTrigger(t) {
  if (wizEhInterrogacao(t)) return false;
  const n = wizNorm(t);
  if (/cancela|cancelar|exclu|conclu|marca como feita|finaliza/.test(n)) return false;
  if (/tarefa/.test(n))
    return /cria\w*|crie|marca|marcar|marque|agende|agendar|adiciona|adicionar|nov[oa]|anota|precisa|coloca/.test(
      n
    );
  if (/(colhe|colher|colheita)/.test(n))
    return /marca|cria\w*|crie|agende|adiciona|para|pra|precisa/.test(n);
  return false;
}
function wizTarCancelTrigger(t) {
  if (wizEhInterrogacao(t)) return false;
  const n = wizNorm(t);
  return /cancela|cancelar|exclu/.test(n) && /tarefa/.test(n);
}
function wizTarefaTitulo(t) {
  return String(t || '')
    .replace(
      /^(cri\w+|marca|marcar|marque|agende|agendar|adicione|adicionar|anota|anotar|coloca|faz|fazer)\s+(uma\s+)?(tarefa\s*(de|para)?)?\s*/i,
      ''
    )
    .replace(/^(a|o|para|pra)\s+/i, '')
    .trim();
}
function wizTarefaChecklist(w) {
  const L = [];
  L.push((w.oque ? '[✓]' : '[ ]') + ' O quê' + (w.oque ? ': ' + w.oque : ''));
  L.push((w.quando ? '[✓]' : '[ ]') + ' Quando' + (w.quando ? ': ' + wizFmtData(w.quando) : ''));
  L.push((w.resp ? '[✓]' : '[ ]') + ' Pra quem' + (w.resp ? ': ' + w.resp : ''));
  return L.join('\n');
}
async function wizTarefaPlano() {
  try {
    const j = await apiFetch('/api/planos-safra/');
    const list = j.results || j || [];
    if (list.length) return list[0].id;
  } catch {}
  try {
    const s = await apiFetch('/api/safras/');
    const list = s.results || s || [];
    if (!list.length) return null;
    const p = await apiFetch('/api/planos-safra/', {
      method: 'POST',
      body: JSON.stringify({ safra: list[0].id }),
    });
    return p.id;
  } catch {
    return null;
  }
}
function wizTarefaStart(texto) {
  const oq = wizTarefaTitulo(texto || '');
  wizTarefa = { step: oq ? 'quando' : 'oque', oque: oq || null, quando: null, resp: null };
  if (oq)
    return `Tarefa: "${oq}" 📝\n${wizTarefaChecklist(
      wizTarefa
    )}\n\nQuando? (ex: hoje, amanhã, sexta, dia 20)`;
  return 'Vamos criar uma tarefa! 📝\n[ ] O quê\n[ ] Quando\n[ ] Pra quem\n\nO que precisa ser feito?';
}
async function wizTarefaStep(texto) {
  const w = wizTarefa;
  const t = (texto || '').trim();
  if (wizCancelar(t)) {
    wizTarefa = null;
    return 'Fluxo cancelado, nada foi criado. 👍';
  }
  const _g = await wizGuardas(WIZ_META.tarefa, 'tarefa', texto);
  if (_g) return _g;
  if (w.step === 'oque') {
    if (!t) return 'O que precisa ser feito? (ex: adubar o talhão Sul)';
    if (wizSim(t) || wizNao(t) || wizNaoEhValor(t))
      return 'Descreva a tarefa (ex: adubar o talhão Sul). O que precisa ser feito?';
    w.oque = wizTarefaTitulo(t) || t;
    w.step = 'quando';
    return `${wizTarefaChecklist(w)}\n\nQuando? (ex: amanhã, sexta, dia 20)`;
  }
  if (w.step === 'quando') {
    // MESMA FABRICA DE DATA do `func:admissao`, e encontrada ao verificar
    // aquele: `!t ? wizHoje()` transformava um Enter em "hoje", gravado no
    // cadastro como data real. Ver o comentario longo em `step === 'admissao'`.
    const dr = t ? wizDataRelativa(t) : null;
    if (!dr) return 'Não entendi a data. Quando? (ex: hoje, amanhã, sexta-feira, dia 20)';
    w.quando = dr;
    w.step = 'resp';
    return `${wizTarefaChecklist(w)}\n\nPra quem é? (nome — ou Enter para pular)`;
  }
  if (w.step === 'resp') {
    const n = wizNorm(t);
    w.resp = !t || /pular|ninguem|sem|equipe toda|todos/.test(n) ? null : t;
    const nome = w.resp ? `${w.oque} (resp. ${w.resp})` : w.oque;
    const planoId = await wizTarefaPlano();
    if (!planoId) {
      wizTarefa = null;
      return 'Não consegui ligar a tarefa (sem safra/plano). Crie uma safra primeiro. 👍';
    }
    try {
      await apiFetch('/api/atividades/', {
        method: 'POST',
        body: JSON.stringify({ plano: planoId, nome, data_prevista: w.quando }),
      });
      wizTarefa = null;
      return `Tarefa criada! ✅ "${nome}" para ${wizFmtData(
        w.quando
      )}.\nPrecisa de mais alguma? (nova tarefa, cancelar, ou outra coisa)`;
    } catch (e) {
      return `Não consegui criar: ${e.message}. Pra quem é? (ou Enter para pular)`;
    }
  }
  wizTarefa = null;
  return 'Vamos recomeçar: diga "criar tarefa".';
}
function wizTarCancelStart() {
  wizTarCancel = { step: 'lista', itens: [] };
  return '__LISTAR__';
}
async function wizTarCancelStep(texto) {
  const c = wizTarCancel;
  const t = (texto || '').trim();
  if (wizCancelar(t)) {
    wizTarCancel = null;
    return 'Fluxo cancelado, nada foi excluído. 👍';
  }
  const _g = await wizGuardas(WIZ_META.tarcancel, 'tarcancel', texto);
  if (_g) return _g;
  if (c.step === 'lista') {
    const list = await wizList('/api/atividades/?concluida=false');
    c.itens = (Array.isArray(list) ? list : []).slice(0, 8);
    if (!c.itens.length) {
      wizTarCancel = null;
      return 'Sem tarefas pendentes — nada pra cancelar. ✅';
    }
    c.step = 'escolha';
    return (
      'Qual cancelar?\n' +
      c.itens.map((x, i) => `${i + 1}. ${x.nome} (${x.data_prevista || 'sem data'})`).join('\n')
    );
  }
  if (c.step === 'escolha') {
    let alvo = null;
    const num = wizParseNum(t);
    if (num && num >= 1 && num <= c.itens.length) alvo = c.itens[Math.round(num) - 1];
    // `t &&` não é defensiva, é o que impede o defeito antigo: com `t`
    // vazio, `nome.includes('')` é sempre verdade, e o Enter cancelava
    // a PRIMEIRA tarefa da lista sem a pessoa ter escolhido nada.
    if (!alvo && t) alvo = wizEscolher(c.itens, t).tal;
    if (!alvo) return 'Qual delas? (diga o número ou parte do nome)';
    c.alvo = alvo;
    c.step = 'conf';
    return `Cancelar "${alvo.nome}"? (sim/não)`;
  }
  if (c.step === 'conf') {
    if (wizSim(t)) {
      try {
        await apiFetch(`/api/atividades/${c.alvo.id}/`, { method: 'DELETE' });
        wizTarCancel = null;
        return `Cancelada! ✅ "${c.alvo.nome}" excluída.`;
      } catch (e) {
        wizTarCancel = null;
        return `Não consegui excluir: ${e.message}.`;
      }
    }
    if (wizNao(t)) {
      wizTarCancel = null;
      return 'Fechado, mantive a tarefa. 👍';
    }
    return `Cancelar "${c.alvo.nome}"? (sim/não)`;
  }
  wizTarCancel = null;
  return 'Vamos recomeçar: diga "cancelar tarefa".';
}
/* troca direta entre fluxos nos pontos de ramificação (ramo/pos) */
function wizTrocaPos(t, kill) {
  // Mesma regra do `wizDetectTroca`: pergunta não é comando.
  if (wizEhInterrogacao(t)) return null;
  if (typeof wizAquaTrigger === 'function' && wizAquaTrigger(t)) {
    kill();
    return wizAquaStart();
  }
  if (typeof wizAnimalTrigger === 'function' && wizAnimalTrigger(t)) {
    kill();
    return wizAnimalStart();
  }
  if (typeof wizTrigger === 'function' && wizTrigger(t)) {
    kill();
    return wizSafraStart(typeof t !== 'undefined' ? t : lastUser);
  }
  if (typeof wizTalhaoTrigger === 'function' && wizTalhaoTrigger(t)) {
    kill();
    return wizTalhaoStart(t);
  }
  if (typeof wizFuncRemTrigger === 'function' && wizFuncRemTrigger(t)) {
    kill();
    return wizFuncRemStart(t);
  }
  if (typeof wizFuncTrigger === 'function' && wizFuncTrigger(t)) {
    kill();
    return wizFuncStart(t);
  }
  if (typeof wizTarefaTrigger === 'function' && wizTarefaTrigger(t)) {
    kill();
    return wizTarefaStart(t);
  }
  return null;
}
/* Lote ambíguo: "cadastrar lote" sem dizer de quê */
let wizLoteQ = false;
function wizLoteAmbiguo(t) {
  const n = wizNorm(t);
  return /\blote\b/.test(n) && /cadastr|cria\w*|crie|nov[oa]|adicion|registr|comec|inici/.test(n);
}
/* ═══════════════════════════════════════════════════════════
   WIZARD SAFRA GUIADA — fluxo conversacional com checklist [✓]
   "cadastrar nova safra" → cultura → nome → talhão → ano → área
   → cria → oferece ciclo produtivo ou IoT (com scan, integração,
   nova estação + API/JSON, estágios com datas e tarefas).
   ═══════════════════════════════════════════════════════════ */
let wizSafra = null;

function wizNorm(s) {
  return String(s || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '');
}
function wizSim(t) {
  const n = wizNorm(t);
  return /^(sim|s|isso|pode|ok|claro|vamos|bora|fechado|fechou|confirmo|confirmado|beleza|blz|show|dale|tanto faz|com certeza|pode ser|por favor|quero|manda)\b/.test(
    n
  );
}
function wizNao(t) {
  const n = wizNorm(t);
  return /^(nao|n|naum|nem|depois|agora nao|por enquanto nao|melhor nao|sei la|deixa|esquece|dispenso|sem isso)\b/.test(
    n
  );
}
function wizCancelar(t) {
  return /\bcancel\w*|\bdesisti(r)?\b|\besquece\b|\bpara tudo\b|\bchega\b|\bsair\b/.test(
    wizNorm(t)
  );
}
/* ═══════════════════════════════════════════════════════════
   PERGUNTA NÃO É RESPOSTA

   O defeito que motivou isto foi dito por um produtor, no meio do
   cadastro de uma safra:

       🤖 Qual o talhão/zona?
       👨 "qual talhão temos disponível para plantar"
       🤖 Não achei talhão "qual talhão temos disponível para
          plantar". Opções: Pastagem - Braquiaria, Reserva Legal,
          Talhao 1 … Qual o talhão?

   São dois defeitos na mesma frase, e o segundo é o pior.

   O PRIMEIRO: a pergunta foi tratada como se fosse a resposta. O
   passo do talhão fazia `nomeDeCadaTalhao.includes(fraseInteira)` —
   a pergunta foi comparada com cada nome, não havia nome nenhum
   dentro dela, e nada casou. Não é um bug deiacento: é um bug de
   TIPO. Uma lista de nomes só casa com nomes.

   O SEGUNDO, que é o que a pessoa viu: a resposta devolvia a
   pergunta ao pé do ouvido. Ela perguntou "quais são os talhões?" e
   recebeu "não achei o talhão que você perguntou — aqui estão os
   talhões". Ou seja: a LISTA DE SEMPRE, com a pergunta colada à
   frente. A lista já estava no ecrã. O que faltava era a frase que
   diz o que fazer a seguir — e o que faltava era não gritar com
   quem não errou.

   Ficam quatro ferramentas, e cada uma fecha um buraco diferente:

     `wizEhPergunta`  — a frase é pergunta sobre as opções, ou
                        pergunta a seco? (porta larga: apanha
                        "está disponível", que não tem ponto de
                        interrogação nem pronome interrogativo)
     `wizEscolher`   — casa a frase com um NOME da lista por PALAVRA
                        inteira, com nota, em vez de `includes` solto
     `wizSemAcerto`  — o que dizer quando não casou: a lista, e o
                        que fazer. Nunca a pergunta de volta.
     `wizDispensavel` — "não tenho", "qualquer um", "pular": ISTO é
                        resposta, e não pode ser lido como pergunta.

   E `wizEhInterrogacao`, mais estreita, para o caso oposto: uma
   pergunta NÃO é um comando de troca de fluxo. "qual talhão temos
   para plantar" contém "plantar", que é verbo de trigger — sem esta
   distinção, a pessoa perguntava e o cadastro saltava para outro.
   ═══════════════════════════════════════════════════════════ */

/* ── 1. A frase é uma PERGUNTA? ──
   Duas portas, de larguras diferentes, porque as duas servem para
   coisas diferentes. `wizEhPergunta` decide se a frase vale como
   RESPOSTA; `wizEhInterrogacao` decide se ela vale como COMANDO.
   Uma frase pode ser as duas coisas ("qual talhão 2?") — e nesse
   caso é resposta, E o fluxo tem de a deixar passar. Por isso a
   porta do comando é estreita: só pronome interrogativo no
   início, "?" ou "me mostra". "cadastrar safra na área que tem
   mais leitura" TEM "tem" e NÃO é uma pergunta — se a porta larga
   bloqueasse a troca de fluxo, uma frase perfeitamente normal deixava
   de trocar de fluxo. */
const WIZ_DUVIDA = /^(qual|quais|quanto|quanta|quantos|quantas|quem|que|como|onde)\b/;
const WIZ_META_PEDIDO =
  /\b(me\s+(diz|diga|fala|fale|mostra|mostre|liste|liste)|mostrar|mostre|listar|liste|opcoes|opcao)\b/;
const WIZ_EXISTE =
  /\b(disponivel|disponiveis|livres|livre|vazios|vazias|vazio|vazia|existe|existem|temos|tenho|ha|sobra|sobram|restam|serve|servem|usar|utilizar|podemos|poderia|dar)\b/;

function wizEhInterrogacao(t) {
  const bruto = String(t || '');
  if (!bruto.trim()) return false;
  if (bruto.indexOf('?') !== -1) return true;
  const n = wizPalavras(bruto);
  return WIZ_DUVIDA.test(n) || WIZ_META_PEDIDO.test(n);
}
function wizEhPergunta(t) {
  if (wizEhInterrogacao(t)) return true;
  const n = wizPalavras(t);
  return !!n && WIZ_EXISTE.test(n);
}

/* ────────────────────────────────────────────────────────────────────────────
   A MEIA METADE QUE FALTAVA: A INSTRUÇÃO
   ────────────────────────────────────────────────────────────────────────────

   MEDIDO 2026-10-04, conduzindo a safra a sério:
   
       "cadastrar uma safra" -> "cultura abobrinha" -> "Escolhe uma"
   
   grava `nome: "Escolhe uma"` e avança. O `wizEhPergunta` não a apanha
   porque "escolhe uma" não é pergunta nenhuma — é uma IMPERATIVAÇÃO, e a
   caixa só tinha porta para as perguntas.

   E "Escolhe uma" não é uma frase que o utilizador inventou: é o que o
   sistema lhe diz noutros sítios (linhas 3808 e 3812: "escolhe os dois e
   confirma"). O utilizador devolve a instrução ao pé do ouvido e ela vira
   dado — que é a classe exacta do defeito do `docs/sistema/10.md`, com
   outra palavra.

   PORQUÊ QUE ANCORAMOS NO INÍCIO
   O imperativo português é verbo-first: "escolhe uma", "sugere um nome".
   Numa RESPOSTA o verbo vem depois do sujeito ("eu prefiro o talhão 2").
   Por isso a âncora é `^`, exactamente como `WIZ_DUVIDA` já faz.

   E porquê esta lista, e não uma mais lata: cada palavra admitida aqui é
   uma palavra que deixa de poder ser um NOME. Acrescentar "qualquer" ou
   "outro" — que aparecem nas frases do sistema — faria "Qualquer
   Transportes" deixar de poder ser um funcionário. A lista é o que a
   auditoria em `tests_pergunta_nao_e_resposta.cjs` mede; se a alastrar,
   essa auditoria tem de mudar no mesmo commit, e é para isso que ela
   existe.

   /*   MEDIDO: os 31 valores legítimos da auditoria são apanhados por esta
   regra ZERO vezes, incluindo "Qualquer", "Quando", "Manuel" e
   "Aluminio" — e também "Manda", "Deixa" e "Escola", que são nomes
   plausíveis e que por isso ficaram FORA da lista.

   NOTA SOBRE A FORMA DOS VERBOS, que é onde se erra duas vezes:
   `preferir` e `sugerir` têm "e" antes do "r" (pref-e-r, sug-e-r), mas na
   1ª pessoa o "e" vira "i": eu **prefiro**, eu **sugiro**. Uma lista
   escrita `prefer(?:o|e)` produz "prefere" e nunca "prefiro". Por isso são
   necessárias as duas raízes — `pref[ei]r` e `suger`/`sugir` — e por isso
   `tests/sondas/sonda_verbo_imperativo.cjs` existe.
*/
const WIZ_IMPERATIVO =
  /^(escolh(?:a|e|o|er|es)|suger(?:ir|es|e|a)|sugir(?:o|a)|pref[ei]r(?:o|es|e|a|ir)|inventa|surpreende)\b/;

function wizEhInstrucao(t) {
  return WIZ_IMPERATIVO.test(wizNorm(t));
}

/**
 * "Isto não serve como valor." A pergunta E a instrução, as duas.
 *
 * Usar ESTE predicado nos passos que GRAVAM TEXTO LIVRE (os `nome`), e não
 * `wizEhPergunta`, é o que fecha as duas metades. Num passo de lista a
 * pergunta dá jeito — a lista é a resposta — e por isso aí se pergunta
 * primeiro `wizEhPergunta` e só depois se procura um item.
 */
function wizNaoEhValor(t) {
  return wizEhPergunta(t) || wizEhInstrucao(t);
}
/* ── 2. As palavras que SÓ são pergunta ──
   A lista é o que se tira antes de tentar casar um nome. Sem ela,
   "qual pastagem temos" casa o talhão "Pastagem - Braquiaria" — o
   `includes` do nome encontra "pastagem" dentro da pergunta, e o
   cadastro grava uma safra no talhão errado sem nunca perguntar. */
const WIZ_PERGUNTA_PALAVRA = new Set([
  // interrogativos
  'qual',
  'quais',
  'quanto',
  'quanta',
  'quantos',
  'quantas',
  'quem',
  'que',
  'como',
  'onde',
  // a pergunta sobre a lista
  'tem',
  'temos',
  'tenho',
  'ha',
  'havia',
  'existe',
  'existem',
  'disponivel',
  'disponiveis',
  'livre',
  'livres',
  'vazio',
  'vazia',
  'sobra',
  'sobram',
  'restam',
  'serve',
  'servem',
  'usar',
  'utilizar',
  'podemos',
  'poderia',
  'dar',
  'dava',
  'mostrar',
  'mostre',
  'listar',
  'liste',
  'opcoes',
  'opcao',
  'seria',
  'fica',
  'fique',
  // o que se está a perguntar
  'talhao',
  'talhoes',
  'tal',
  'zona',
  'zonas',
  'cultura',
  'culturas',
  'safra',
  'safras',
  'pessoa',
  'pessoas',
  'funcionario',
  'funcionarios',
  'lote',
  'lotes',
  'area',
  'areas',
  'ano',
  'anos',
  'hectare',
  'hectares',
  'hect',
  'nome',
  'nomes',
  'registro',
  'registros',
  'cadastro',
  'cadastrar',
  'plantio',
  'plantar',
  'cultivo',
  'colheita',
  'colher',
  'sistema',
  'raca',
  'especie',
  'tipo',
  'ambiente',
  'tanque',
  'viveiro',
  'estacao',
  'estacoes',
  'estagio',
  'estagios',
  'tarefa',
  'tarefas',
  'funcao',
  'cargo',
  'salario',
  'telefone',
  'data',
  'datas',
  'hora',
  'quantidade',
  'peso',
  'biomassa',
  // ligação — nunca fazem parte de um nome
  'a',
  'o',
  'as',
  'os',
  'um',
  'uma',
  'uns',
  'umas',
  'no',
  'na',
  'nos',
  'nas',
  'do',
  'da',
  'dos',
  'das',
  'em',
  'de',
  'para',
  'pra',
  'pro',
  'com',
  'sem',
  'e',
  'ou',
  'mas',
  'me',
  'se',
  'lhe',
  'vos',
  'aqui',
  'ali',
  'la',
  'ai',
  'nele',
  'nela',
  'dele',
  'dela',
  'vamos',
  'vou',
  'quero',
  'queria',
  'queremos',
  'pode',
  'podem',
  'devo',
  'devemos',
  'novo',
  'nova',
  'outro',
  'outra',
  'ser',
  'estar',
  'ficou',
  'esta',
  'to',
  'ta',
  'foi',
]);

/* ── 3. Casar a frase com um NOME, por PALAVRA ──
   O `includes` antigo (`nome.includes(texto) || texto.includes(nome)`)
   casa por qualquer substring, e isso tem duas consequências ruins:

     `texto.includes("1")`  →  casa com "Talhao 1", "Talhao 10" e
                               "Safra 2026" ao mesmo tempo;
     `nome.includes(texto)` →  casa um nome inteiro dentro de uma
                               frase, que é o caminho do bug acima.

   Aqui o casamento é por palavra inteira, e com nota, para que um
   nome exacto ganhe a um nome parcial e a desambiguação só aconteça
   entre candidatos com a MESMA nota. */
function wizPalavras(s) {
  return wizNorm(s)
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}
/* palavra inteira, não pedaço de palavra */
function wizDentro(agulha, palheiro) {
  if (!agulha) return false;
  return (' ' + palheiro + ' ').indexOf(' ' + agulha + ' ') !== -1;
}
/* o que sobra da frase quando se tira a pergunta */
function wizResiduo(t) {
  return wizPalavras(t)
    .split(' ')
    .filter((w) => w && !WIZ_PERGUNTA_PALAVRA.has(w))
    .join(' ');
}
function wizAcharNome(lista, t) {
  const entrada = wizPalavras(t);
  if (!entrada) return [];
  const sobra = wizResiduo(t);
  // Uma PERGUNTA só pode casar pelo que DIZ, nunca pelo que sobra.
  //
  // "qual pastagem temos" sobra a palavra "pastagem" depois de se tirar
  // "qual" e "temos" — e essa palavra, sozinha, casava o talhão
  // "Pastagem - Braquiaria". A safra acabava gravada no talhão errado
  // sem ninguém ter escolhido nada: "pastagem" é o que sobra, não é o
  // que a pessoa disse.
  //
  // Sobram duas portas de entrada, e são as duas que não inventam:
  // o nome EXACTO ("Pastagem - Braquiaria") e o nome INTEIRO dito
  // dentro da frase ("coloca no Talhao 1 - Catuai Vermelho"). Uma
  // pergunta nunca é nenhuma das duas.
  const perguntou = wizEhPergunta(entrada);
  const forte = entrada.split(' ').filter((w) => w.length >= 4 && !WIZ_PERGUNTA_PALAVRA.has(w));
  const achados = [];
  for (const item of Array.isArray(lista) ? lista : []) {
    if (!item) continue;
    const nn = wizPalavras(item.nome || item.name || item.title || '');
    if (!nn) continue;
    let nota = 0;
    if (entrada === nn) nota = 100;
    else if (wizDentro(nn, entrada)) nota = 90;
    else if (!perguntou && sobra && sobra === nn) nota = 80;
    else if (!perguntou && sobra && wizDentro(nn, sobra)) nota = 70;
    else if (!perguntou && sobra && wizDentro(sobra, nn)) nota = 60;
    // Só com palavra distintiva, e só quando SOBROU alguma coisa. A
    // segunda condição é o que impede "qual pastagem temos" (que não
    // sobra nada) de casar a talhão "Pastagem - Braquiaria": sem ela a
    // pergunta ganhava um registo sem ninguém perguntar.
    else if (!perguntou && sobra && forte.length) {
      const forteNome = nn.split(' ').filter((w) => w.length >= 4);
      if (forte.some((w) => forteNome.indexOf(w) !== -1)) nota = 40;
    }
    if (nota) achados.push({ item, nota });
  }
  achados.sort((a, b) => b.nota - a.nota);
  return achados;
}
/* `tal` é o registo escolhido; `alternativa` só vem preenchida quando
   DOIS OU MAIS candidatos empataram na nota — é aí que o fluxo tem de
   perguntar "qual deles?". Nunca devolve um palpite. */
function wizEscolher(lista, t) {
  const ranked = wizAcharNome(lista, t);
  if (!ranked.length) return { tal: null, alternativa: [] };
  const melhores = ranked.filter((r) => r.nota === ranked[0].nota);
  if (melhores.length === 1) return { tal: ranked[0].item, alternativa: [] };
  return { tal: null, alternativa: melhores.map((r) => r.item) };
}

/* ── 4. "Não tenho" É RESPOSTA ──
   Vem ANTES de `wizEhPergunta` de propósito. "não tenho talhão" e
   "qualquer um" contêm palavras de pergunta — "tem", "qualquer" — e
   sem esta porta uma frase que É resposta seria tratada como
   pergunta, e o cadastro nunca mais saía do talhão.

   `sem <algo>` está aqui, e não num `\bsem\b` genérico, porque
   "sem" é uma palavra que aparece em nomes a sério ("Várzea do
   Sem Fim"). Só conta para os registos que o cadastro sabe
   dispensar — e o passo do talhão SOBRAVA "sem talhão" sem dizer
   isto, que é um caminho que só o teste apanha. */
const WIZ_DISPENSAVEL =
  /\b(pular|pula|pulei|ninguem|nao\s+nenhum|nenhum|nenhuma|qualquer|deixa|deixar|dispenso|sei\s+la|em\s+breve|mais\s+tarde|logo\s+depois)\b/;
const WIZ_SEM_REGISTO =
  /\bsem\s+(talhao|talhoes|zona|zonas|cultura|culturas|lote|lotes|funcionario|funcionarios|tarefa|tarefas)\b/;
function wizDispensavel(t) {
  if (wizNao(t)) return true;
  const n = wizPalavras(t);
  return WIZ_DISPENSAVEL.test(n) || WIZ_SEM_REGISTO.test(n);
}

/* ── 5. O que dizer quando a frase não era um nome ──
   Duas respostas para dois erros diferentes, e nenhuma das duas
   devolve a frase ao pé do ouvido do produtor:
     · era PERGUNTA → a lista, e o que fazer com a lista;
     · era um NOME que não existe → a lista, e o erro sem a pergunta
       colada. O eco curto só entra em nome CURTO e não-pergunta,
       porque aí ajuda ("não achei 'catui'" diz o que escrever a
       seguir). */
function wizNomes(lista, max) {
  return (Array.isArray(lista) ? lista : [])
    .map((x) => (x && (x.nome || x.name)) || '')
    .filter(Boolean)
    .slice(0, max || 8);
}
function wizEcoCurto(t) {
  const s = String(t || '')
    .trim()
    .replace(/\s+/g, ' ');
  if (!s || s.length > 24) return '';
  if (wizEhPergunta(s)) return '';
  return ` "${s}"`;
}
function wizSemAcerto(oQue, lista, t, vira) {
  const nomes = wizNomes(lista, 8);
  if (!nomes.length) {
    return `Não há ${oQue} cadastrado ainda — quer cadastrar primeiro, ou seguimos sem ${
      vira || 'isso'
    }?`;
  }
  const listaFmt = nomes.map((n, i) => `${i + 1}. ${n}`).join('\n');
  const pular = vira ? `\n\nDiga o nome, ou "pular" para seguir sem ${vira}.` : '\n\nQual deles?';
  return `Não achei ${oQue}${wizEcoCurto(t)}.\n${listaFmt}${pular}`;
}
function wizComPergunta(oQue, lista, pergunta, vira) {
  const nomes = wizNomes(lista, 8);
  if (!nomes.length) return null; // não há lista para responder à pergunta
  const listaFmt = nomes.map((n, i) => `${i + 1}. ${n}`).join('\n');
  const fim = vira ? `\n\nDiga o nome, ou "pular" para seguir sem ${vira}.` : '\n\nQual deles?';
  return `${pergunta}\n${listaFmt}${fim}`;
}
function wizTrigger(t) {
  // Uma pergunta não abre um cadastro. "qual talhão temos disponível
  // para plantar" traz "plantar", que é o verbo desta trigger — sem
  // esta linha a pessoa que perguntou recebia o cadastro de safra a
  // abrir-se à frente dela.
  if (wizEhInterrogacao(t)) return false;
  const n = wizNorm(t);
  if (!/(safra|plantio|plantacao|cultivo|plantar)/.test(n)) return false;
  return /cadastr|cria\w*|crie|nov[oa]|adicion|registr|comec|inici|plant/.test(n);
}
function wizChecklist(w) {
  const L = [];
  L.push((w.cultura ? '[✓]' : '[ ]') + ' Cultura' + (w.cultura ? ': ' + w.cultura.nome : ''));
  L.push((w.nome ? '[✓]' : '[ ]') + ' Nome da safra' + (w.nome ? ': ' + w.nome : ''));
  L.push((w.talhao ? '[✓]' : '[ ]') + ' Talhão/Zona' + (w.talhao ? ': ' + w.talhao.nome : ''));
  L.push((w.ano ? '[✓]' : '[ ]') + ' Ano' + (w.ano ? ': ' + w.ano : ''));
  L.push((w.area ? '[✓]' : '[ ]') + ' Área plantada' + (w.area ? ': ' + w.area + ' ha' : ''));
  return L.join('\n');
}
async function wizList(url) {
  try {
    const j = await apiFetch(url);
    if (Array.isArray(j)) return j;
    return j.results || j.data || [];
  } catch {
    return [];
  }
}
/* ── busca cultura atravessando a paginação (707 culturas não cabem na 1ª página) ──
   Usa ?search= do servidor (filtra TODAS) + fallback local na 1ª página. */
async function wizBuscarCultura(t) {
  const q = wizNorm(t).trim();
  if (!q) return [];
  // Uma pergunta não é uma cultura. Sem esta porta, "?search=qual
  // cultura temos" ia ao servidor e o servidor — que faz busca por
  // substring — podia responder com cultura nenhuma e o fluxo
  // avançava com a primeira. O fallback local (abaixo) já casa por
  // palavra; esta é a mesma regra no caminho do servidor.
  if (wizEhPergunta(t) && !wizResiduo(t)) return [];
  try {
    const js = await apiFetch(
      '/api/culturas/?dedupe=1&search=' + encodeURIComponent(String(t || '').trim())
    );
    const arr = Array.isArray(js) ? js : js.results || js.data || [];
    if (arr.length) return arr;
  } catch {}
  try {
    const list = await wizList('/api/culturas/?dedupe=1');
    return wizAcharNome(list, q).map((r) => r.item);
  } catch {
    return [];
  }
}
const WIZ_STOP_CULTURA = [
  'cadastrar',
  'cadastro',
  'cadastr',
  'safra',
  'plantio',
  'plantar',
  'cultivo',
  'cultivar',
  'cultura',
  'ano',
  'talhao',
  'vincular',
  'vincula',
  'liga',
  'ligar',
  'para',
  'de',
  'da',
  'do',
  'das',
  'dos',
  'em',
  'no',
  'na',
  'uma',
  'novo',
  'nova',
  'meu',
  'minha',
  'e',
  'com',
  'que',
];
async function wizPrefillCultura(texto) {
  // Palavra candidata de trás pra frente: "safra de arroz" → arroz
  const words = wizNorm(texto)
    .split(/[^a-z0-9]+/)
    .filter((w) => w.length > 2 && !WIZ_STOP_CULTURA.includes(w));
  for (let i = words.length - 1; i >= 0; i--) {
    try {
      const js = await apiFetch('/api/culturas/?search=' + encodeURIComponent(words[i]));
      const arr = Array.isArray(js) ? js : js.results || js.data || [];
      if (arr.length) return arr[0];
    } catch {}
  }
  return null;
}
/* ── datas robustas: dd/mm/aaaa, dd-mm-aaaa, ISO, dd/mm, "15 de outubro",
   "dia 15", "mês que vem", hoje/ontem/amanhã — sempre validadas ── */
function wizHoje() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(
    d.getDate()
  ).padStart(2, '0')}`;
}
function wizFmtData(iso) {
  const p = String(iso || '').split('-');
  return p.length === 3 ? `${p[2]}/${p[1]}/${p[0]}` : String(iso || '');
}
function wizSomarDias(iso, dias) {
  const [a, m, d] = String(iso).split('-').map(Number);
  const dt = new Date(a, m - 1, d + dias);
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(
    dt.getDate()
  ).padStart(2, '0')}`;
}
function wizDataValida(a, m, d) {
  a = +a;
  m = +m;
  d = +d;
  if (!(a >= 1900 && a <= 2101) || !(m >= 1 && m <= 12) || !(d >= 1 && d <= 31)) return false;
  const dt = new Date(a, m - 1, d);
  return dt.getFullYear() === a && dt.getMonth() === m - 1 && dt.getDate() === d;
}
const WIZ_MESES = {
  janeiro: '01',
  fevereiro: '02',
  marco: '03',
  abril: '04',
  maio: '05',
  junho: '06',
  julho: '07',
  agosto: '08',
  setembro: '09',
  outubro: '10',
  novembro: '11',
  dezembro: '12',
};
function wizParseDatas(t) {
  const out = [];
  const push = (a, m, d) => {
    m = String(m).padStart(2, '0');
    d = String(d).padStart(2, '0');
    const iso = `${a}-${m}-${d}`;
    if (wizDataValida(a, m, d) && !out.includes(iso) && out.length < 2) out.push(iso);
  };
  const n = wizNorm(String(t || ''));
  const H = wizHoje().split('-').map(Number);
  if (/\bhoje\b/.test(n)) push(H[0], H[1], H[2]);
  if (/\bontem\b/.test(n)) {
    const p = wizSomarDias(wizHoje(), -1).split('-');
    push(p[0], p[1], p[2]);
  }
  if (/\bamanha\b/.test(n)) {
    const p = wizSomarDias(wizHoje(), 1).split('-');
    push(p[0], p[1], p[2]);
  }
  if (/mes que vem/.test(n)) {
    const p = wizSomarDias(wizHoje(), 30).split('-');
    push(p[0], p[1], p[2]);
  }
  let m;
  const reIso = /(\d{4})-(\d{1,2})-(\d{1,2})/g;
  while ((m = reIso.exec(n)) && out.length < 2) push(m[1], m[2], m[3]);
  const reFull = /(\d{1,2})[\/.\-](\d{1,2})[\/.\-](\d{2,4})/g;
  while ((m = reFull.exec(n)) && out.length < 2) {
    if (m.index > 0 && /\d/.test(n[m.index - 1])) continue; // pedaço de ISO (25-10-15 de 2025-10-15)
    if (m[1].length === 4) continue; // ISO já tratada
    const c = m[3].length === 2 ? '20' + m[3] : m[3];
    push(c, m[2], m[1]);
  }
  const reCurta = /(\d{1,2})[\/.](\d{1,2})(?![\/.\-\d])/g;
  while ((m = reCurta.exec(n)) && out.length < 2) push(H[0], m[2], m[1]);
  const reExt = /(\d{1,2})\s+de\s+([a-z]+)(?:\s+de\s+(\d{2,4}))?/g;
  while ((m = reExt.exec(n)) && out.length < 2) {
    const mm = WIZ_MESES[m[2]];
    if (!mm) continue;
    push(m[3] ? (m[3].length === 2 ? '20' + m[3] : m[3]) : H[0], mm, m[1]);
  }
  const reDia = /\bdia\s+(\d{1,2})\b/g;
  while ((m = reDia.exec(n)) && out.length < 2) push(H[0], H[1], m[1]);
  return out;
}
/* ── números robustos: "12,5", "R$ 3.000", "2 mil", "dez", "vinte e cinco" ── */
const WIZ_EXTENSO = {
  um: 1,
  uma: 1,
  dois: 2,
  duas: 2,
  tres: 3,
  quatro: 4,
  cinco: 5,
  seis: 6,
  meia: 0.5,
  meio: 0.5,
  sete: 7,
  oito: 8,
  nove: 9,
  dez: 10,
  onze: 11,
  doze: 12,
  treze: 13,
  catorze: 14,
  quatorze: 14,
  quinze: 15,
  dezesseis: 16,
  dezessete: 17,
  dezoito: 18,
  dezenove: 19,
  vinte: 20,
  trinta: 30,
  quarenta: 40,
  cinquenta: 50,
  sessenta: 60,
  setenta: 70,
  oitenta: 80,
  noventa: 90,
  cem: 100,
  cento: 100,
  duzentos: 200,
  trezentos: 300,
  quatrocentos: 400,
  quinhentos: 500,
};
function wizParseNum(t) {
  let s = String(t || '').toLowerCase();
  let mult = 1;
  if (/milh/.test(s)) mult = 1000000;
  else if (/\bmil\b/.test(s)) mult = 1000;
  s = s.replace(/(\d)\.(\d{3})(?=\D|$)/g, '$1$2'); // milhar BR: 3.000 → 3000
  const m = s.replace(',', '.').match(/(\d+(?:\.\d+)?)/);
  let v = m ? parseFloat(m[1]) : null;
  if (v == null) {
    if (/\bmil\b/.test(s)) return 1000; // "mil cabeças"
    const words = wizNorm(s).split(/[\s-]+/);
    let tot = 0,
      cur = 0,
      found = false;
    for (const wdd of words) {
      if (wdd === 'e') continue;
      const vv = WIZ_EXTENSO[wdd];
      if (vv == null) continue; // ignora unidade/recheio ("doze hectares e meio" → 12.5)
      found = true;
      if (vv === 100 && cur > 0) cur *= 100;
      else cur += vv;
      if (vv >= 100) {
        tot += cur;
        cur = 0;
      }
    }
    if (found) v = tot + cur || null;
  }
  if (v == null) return null;
  return v * mult;
}
function wizEui() {
  const h = '0123456789ABCDEF';
  let s = '';
  for (let i = 0; i < 16; i++) s += h[Math.floor(Math.random() * 16)];
  return s;
}
/* ═══════════════════════════════════════════════════════════
   MAQUINARIA DE ROBUSTEZ — voltar, ajuda, troca de fluxo,
   confirmação de valores estranhos. Compartilhada pelos
   wizards safra/animal/aquático.
   ═══════════════════════════════════════════════════════════ */
const WIZ_Q_SAFRA = {
  cultura: 'Qual a cultura?',
  nome: 'Qual o nome da safra?',
  talhao: 'Qual o talhão/zona?',
  ano: 'Qual o ano da safra?',
  area: 'Qual a área plantada em ha?',
  datas_p: 'Qual a data do plantio? (ou Enter para pular)',
  datas_c: 'E a previsão de colheita? (ou Enter para pular)',
  ramo: 'Vamos continuar para o ciclo produtivo ou IoT?',
  ciclo_nome: 'Qual o nome do estágio?',
  ciclo_datas: 'Quais são as datas de início e término do estágio? (ex: 12/09/2025 até 12/02/2026)',
  ciclo_tarefa_q: 'Quer associar tarefas desse estágio aos seus funcionários? (sim/não)',
  ciclo_tarefa: 'Qual tarefa e para quem? (ex: associe a poda aos técnicos agrícolas)',
  ciclo_mais: 'Quer cadastrar mais tarefas? (sim/não)',
  iot_integrar: 'Quer que eu integre os dados dela a esta safra? (sim/não)',
  iot_nova_q: 'Quer cadastrar uma nova estação? (ex: umidade do solo e ambiente)',
  iot_nova: 'Qual estação? (ex: umidade do solo e ambiente)',
  pos: 'O que mais? (novo estágio, IoT, ou outra coisa)',
};
const WIZ_Q_ANIMAL = {
  especie: 'Qual a espécie? (boi, suíno, ovino, frango…)',
  tipo: 'Qual o tipo de produção? (corte, leite, ovos — Enter = corte)',
  raca: 'Qual a raça? (Enter = pular)',
  qtd: 'Quantas cabeças?',
  peso: 'Peso médio em kg? (Enter = pular)',
  data: 'Data de entrada? (dd/mm/aaaa — ou diga "hoje")',
  ramo: 'Quer cadastrar um piquete, registrar produção, ou fechar?',
  piq_nome: 'Qual o nome do piquete?',
  piq_area: 'Qual a área do piquete em ha?',
  piq_cap: 'Qual a capacidade em UA/ha? (Enter = 1,0)',
  piq_talhao: 'Esse piquete fica em qual talhão? (ou Enter para pular)',
  prod_data: 'Qual a data da produção? (dd/mm/aaaa — ou diga "hoje")',
  prod_qtd: 'Quantidade e unidade? (ex: 120 litros)',
  prod_valor: 'Valor estimado em R$? (Enter = pular)',
  pos: 'O que mais? (outra produção, piquete, ou fechar)',
};
const WIZ_Q_AQUA = {
  especie: 'Qual a espécie? (tilápia, tambaqui, carpa, camarão…)',
  sistema:
    'Qual o sistema? (viveiro, tanque-rede, tanque elevado, aquaponia, bioflocos — Enter = viveiro)',
  ambiente: 'Qual o tanque/viveiro? (nome — Enter = pular)',
  qtd: 'Quantidade de alevinos/peixes?',
  biomassa: 'Peso médio por peixe em gramas? (Enter = pular)',
  data: 'Data do povoamento? (dd/mm/aaaa — ou diga "hoje")',
  ramo: 'Quer registrar uma despesca ou fechar?',
  desp_data: 'Qual a data da despesca? (dd/mm/aaaa — ou diga "hoje")',
  desp_kg: 'Quantos kg foram despescados?',
  desp_valor: 'Valor estimado em R$? (Enter = pular)',
  pos: 'O que mais? (outra despesca, novo lote, ou fechar)',
};
const WIZ_HELP = {
  safra:
    'Aqui a gente cadastra safra passo a passo: cultura → nome → talhão → ano → área → plantio/colheita → ciclo ou IoT.',
  animal:
    'Aqui a gente cadastra lote passo a passo: espécie → produção → raça → cabeças → peso → entrada → piquete e/ou produção.',
  aqua: 'Aqui a gente cadastra lote aquícola passo a passo: espécie → sistema → ambiente → quantidade → povoamento → despesca.',
  talhao:
    'Aqui a gente cadastra talhão: nome → área → cultura (opcional). Dá pra vincular cultura depois.',
  vinc: 'Aqui a gente liga cultura e talhão: escolhe os dois e confirma.',
  func: 'Aqui a gente cadastra funcionário: nome → função → salário → admissão → telefone (opcional).',
  funcrem: 'Aqui a gente remove alguém da equipe: acha o nome, confirma, e desativa.',
  tarefa: 'Aqui a gente cria tarefa: o quê → quando (vale "amanhã", "sexta", "dia 20") → pra quem.',
  tarcancel: 'Aqui a gente cancela tarefa: lista as pendentes, escolhe e confirma.',
};
const WIZ_TROCA_LABEL = {
  aqua: 'cadastrar peixe',
  animal: 'cadastrar rebanho',
  safra: 'cadastrar safra',
  talhao: 'cadastrar talhão',
  vinc: 'vincular cultura',
  func: 'cadastrar funcionário',
  funcrem: 'remover funcionário',
  tarefa: 'criar tarefa',
  tarcancel: 'cancelar tarefa',
};
const WIZ_META = {
  safra: {
    get: () => wizSafra,
    kill: () => {
      wizSafra = null;
    },
    Q: WIZ_Q_SAFRA,
    data: [
      'cultura',
      'nome',
      'talhao',
      'ano',
      'area',
      'safra',
      'estagios',
      'estagio',
      'dev',
      'candidatos',
      'registroId',
    ],
    livres: ['ramo', 'pos', 'iot_integrar', 'iot_nova_q', 'ciclo_tarefa_q', 'ciclo_mais'],
    start: () => wizSafraStart(),
    fluxo: 'da safra',
    outro: { aqua: 'cadastrar peixe', animal: 'cadastrar rebanho' },
    cancele: 'Fluxo cancelado. Quando quiser, é só dizer "cadastrar nova safra".',
  },
  animal: {
    get: () => wizAnimal,
    kill: () => {
      wizAnimal = null;
    },
    Q: WIZ_Q_ANIMAL,
    data: [
      'especie',
      'tipo',
      'raca',
      'qtd',
      'peso',
      'data',
      'lote',
      'piqNome',
      'piqArea',
      'piqCap',
      'prodData',
      'prodQtd',
      'prodUn',
    ],
    livres: ['ramo', 'pos'],
    start: () => wizAnimalStart(),
    fluxo: 'do lote',
    outro: { aqua: 'cadastrar peixe', safra: 'cadastrar safra' },
    cancele: 'Fluxo cancelado. Quando quiser, é só dizer "cadastrar rebanho".',
  },
  aqua: {
    get: () => wizAqua,
    kill: () => {
      wizAqua = null;
    },
    Q: WIZ_Q_AQUA,
    data: [
      'especie',
      'sistema',
      'ambiente',
      'qtd',
      'biomassa',
      'data',
      'lote',
      'despData',
      'despKg',
    ],
    livres: ['ramo', 'pos'],
    start: () => wizAquaStart(),
    fluxo: 'do lote aquícola',
    outro: { animal: 'cadastrar rebanho', safra: 'cadastrar safra' },
    cancele: 'Fluxo cancelado. Quando quiser, é só dizer "cadastrar peixe".',
  },
  talhao: {
    get: () => wizTalhaoF,
    kill: () => {
      wizTalhaoF = null;
    },
    Q: {
      nome: 'Qual o nome do talhão?',
      area: 'Qual a área do talhão em ha?',
      cultura: 'Alguma cultura nele? (nome — ou Enter para pular)',
      vinc: 'Qual cultura vincular ao talhão?',
      pos: 'O que mais? (vincular cultura, novo talhão, ou fechar)',
    },
    data: ['nome', 'area', 'cultura', 'talhaoId'],
    livres: ['pos'],
    start: (t) => wizTalhaoStart(t),
    fluxo: 'do talhão',
    outro: { safra: 'cadastrar safra', animal: 'cadastrar rebanho', aqua: 'cadastrar peixe' },
    cancele: 'Fluxo cancelado. Quando quiser, é só dizer "cadastrar talhão".',
  },
  vinc: {
    get: () => wizVinc,
    kill: () => {
      wizVinc = null;
    },
    Q: {
      cultura: 'Qual a cultura?',
      talhao: 'Em qual talhão?',
      conf: 'Confirma o vínculo? (sim/não)',
    },
    data: ['cultura', 'talhao'],
    livres: [],
    start: (t) => wizVincStart(t),
    fluxo: 'do vínculo',
    outro: { safra: 'cadastrar safra', animal: 'cadastrar rebanho', aqua: 'cadastrar peixe' },
    cancele: 'Fluxo cancelado.',
  },
  func: {
    get: () => wizFunc,
    kill: () => {
      wizFunc = null;
    },
    Q: {
      nome: 'Qual o nome?',
      cargo: 'Qual a função?',
      salario: 'Qual o salário em R$? (ou "a combinar")',
      admissao: 'Data de admissão? (dd/mm/aaaa — obrigatório)',
      fone: 'Telefone/WhatsApp? (Enter = pular)',
    },
    data: ['nome', 'cargo', 'salario', 'admissao', 'fone'],
    livres: [],
    start: (t) => wizFuncStart(t),
    fluxo: 'do funcionário',
    outro: { safra: 'cadastrar safra', animal: 'cadastrar rebanho', aqua: 'cadastrar peixe' },
    cancele: 'Fluxo cancelado.',
  },
  funcrem: {
    get: () => wizFuncRem,
    kill: () => {
      wizFuncRem = null;
    },
    Q: { alvo: 'Quem sai da equipe?', conf: 'Confirma a remoção? (sim/não)' },
    data: ['nome', 'alvo'],
    livres: [],
    start: (t) => wizFuncRemStart(t),
    fluxo: 'da remoção',
    outro: { safra: 'cadastrar safra', animal: 'cadastrar rebanho', aqua: 'cadastrar peixe' },
    cancele: 'Fluxo cancelado, ninguém foi removido. 👍',
  },
  tarefa: {
    get: () => wizTarefa,
    kill: () => {
      wizTarefa = null;
    },
    Q: {
      oque: 'O que precisa ser feito?',
      quando: 'Quando? (ex: amanhã, sexta, dia 20)',
      resp: 'Pra quem é? (ou Enter para pular)',
    },
    data: ['oque', 'quando', 'resp'],
    livres: [],
    start: (t) => wizTarefaStart(t),
    fluxo: 'da tarefa',
    outro: { safra: 'cadastrar safra', animal: 'cadastrar rebanho', aqua: 'cadastrar peixe' },
    cancele: 'Fluxo cancelado, nada foi criado. 👍',
  },
  tarcancel: {
    get: () => wizTarCancel,
    kill: () => {
      wizTarCancel = null;
    },
    Q: {
      lista: 'Buscando pendentes...',
      escolha: 'Qual delas? (número ou nome)',
      conf: 'Confirma? (sim/não)',
    },
    data: ['itens', 'alvo'],
    livres: [],
    start: () => wizTarCancelStart(),
    fluxo: 'do cancelamento',
    outro: { safra: 'cadastrar safra', animal: 'cadastrar rebanho', aqua: 'cadastrar peixe' },
    cancele: 'Fluxo cancelado, nada foi excluído. 👍',
  },
};
/* ── Passos que escolhem um registo de uma LISTA ──
   Nestes, uma pergunta sobre a lista é uma pergunta — e a resposta
   certa é a LISTA, não um palpite de nome. Fica declarado aqui, e
   não espalhado pelos passos, por uma razão prática: os passos que
   tratam listas são oito, e cada um tinha a sua cópia (diferente)
   do `includes` e da mensagem de "não achei". Um tabela só é um
   lugar só para corrigir.

   `pular` diz o que fica de fora do passo quando a pessoa responde
   "não tenho" — e é o que a mensagem oferece à mesma pessoa que
   perguntou. Uma lista sem `pular` seria uma pergunta sem saída. */
const WIZ_PASSOS_LISTA = {
  'safra:cultura': {
    url: '/api/culturas/',
    oQue: 'essa cultura',
    pergunta: 'Qual a cultura?',
    pular: 'cultura',
  },
  'safra:talhao': {
    url: '/api/talhoes/',
    oQue: 'esse talhão',
    pergunta: 'Qual o talhão/zona?',
    pular: 'talhão',
  },
  'vinc:cultura': { url: '/api/culturas/', oQue: 'essa cultura', pergunta: 'Qual a cultura?' },
  'vinc:talhao': { url: '/api/talhoes/', oQue: 'esse talhão', pergunta: 'Em qual talhão?' },
  'talhao:cultura': {
    url: '/api/culturas/',
    oQue: 'essa cultura',
    pergunta: 'Qual a cultura do talhão?',
    pular: 'cultura',
  },
  'funcrem:alvo': {
    url: '/api/funcionarios/',
    oQue: 'ninguém com esse nome',
    pergunta: 'Quem sai da equipe?',
  },
};
function wizSnap(F) {
  const f = F.get();
  const o = { step: f.step };
  for (const k of F.data) o[k] = f[k] === undefined ? null : f[k];
  return o;
}
function wizRestore(F, s) {
  const f = F.get();
  for (const k of F.data) f[k] = s[k];
  f.step = s.step;
  delete f.pendConfirm;
}
function wizTrack(F) {
  const f = F.get();
  if (!f.hist) f.hist = [];
  const raw = JSON.stringify(wizSnap(F));
  const last = f.hist[f.hist.length - 1];
  if (!last || last.raw !== raw) {
    f.hist.push({ raw });
    if (f.hist.length > 12) f.hist.shift();
  }
}
function wizQuerVoltar(t) {
  return /\bvoltar\b|\bvolta\b|\banterior\b|\berrei\b|\bcorrigir\b|\bcorrige\b|\bmudei de ideia\b|\btrocar\b/.test(
    wizNorm(t)
  );
}
function wizVoltar(F) {
  const f = F.get();
  const H = f.hist || [];
  const cur = f.step;
  while (H.length) {
    const top = JSON.parse(H[H.length - 1].raw);
    if (top.step !== cur) break;
    H.pop();
  }
  if (!H.length) return 'Estamos no começo — ' + (F.Q[cur] || 'vamos lá.');
  const prev = JSON.parse(H.pop().raw);
  wizRestore(F, prev);
  return 'Voltei! ↩️ ' + (F.Q[prev.step] || 'continuando.');
}
function wizQuerAjuda(t) {
  return /ajuda|help|socorro|como funciona|como usa|nao entendi|repete|de novo|quais opcoes|que opcoes|o que (voce|vc|tu) (pode|faz|sabe)|h\?|hein\??$/.test(
    wizNorm(t)
  );
}
/* confirmação genérica: aplicar() executa no "sim"; recusa no "não" */
async function wizVerConfirm(F, t) {
  const f = F.get();
  if (!f.pendConfirm) return null;
  if (wizCancelar(t)) {
    f.pendConfirm = null;
    F.kill();
    return F.cancele;
  }
  const pc = f.pendConfirm;
  f.pendConfirm = null;
  if (wizSim(t)) return await pc.aplicar();
  if (wizNao(t)) return pc.recusa || 'Ok, sem problema. ' + (F.Q[f.step] || '');
  f.pendConfirm = pc;
  return pc.pergunta || 'Confirma? (sim/não)';
}
function wizArmarConfirm(F, pergunta, aplicar, recusa) {
  F.get().pendConfirm = { pergunta, aplicar, recusa };
  return pergunta;
}
/* troca de fluxo no meio do caminho (todos os fluxos) */
let wizSwitch = null;
/* Uma pergunta NÃO troca de fluxo.
   "qual talhão temos disponível para plantar" contém "plantar", que é
   verbo de trigger da safra. Sem esta guarda, a pessoa que perguntou
   quem tinha disponível recebia "Quer largar e cadastrar uma safra?" —
   o cadastro a saltava para outro fluxo por causa de uma PERGUNTA.
   Só a porta estreita (`wizEhInterrogacao`) corta, e não a larga:
   "cadastrar safra na área que tem mais leitura" não é pergunta e tem
   de continuar a trocar. */
function wizDetectTroca(t, exceto) {
  if (wizEhInterrogacao(t)) return null;
  if (exceto !== 'aqua' && wizAquaTrigger(t)) return 'aqua';
  if (exceto !== 'animal' && wizAnimalTrigger(t)) return 'animal';
  if (exceto !== 'talhao' && wizTalhaoTrigger(t)) return 'talhao';
  if (exceto !== 'vinc' && wizVincTrigger(t)) return 'vinc';
  if (exceto !== 'funcrem' && wizFuncRemTrigger(t)) return 'funcrem';
  if (exceto !== 'func' && wizFuncTrigger(t)) return 'func';
  if (exceto !== 'tarcancel' && wizTarCancelTrigger(t)) return 'tarcancel';
  if (exceto !== 'tarefa' && wizTarefaTrigger(t)) return 'tarefa';
  if (exceto !== 'safra' && wizTrigger(t)) return 'safra';
  return null;
}
/* guardas de entrada — chamar no topo de cada wiz*Step após o cancelar */
async function wizGuardas(F, flowKey, texto) {
  const f = F.get();
  wizTrack(F);
  if (wizSwitch) {
    const sw = wizSwitch;
    wizSwitch = null;
    if (wizCancelar(texto)) {
      F.kill();
      return F.cancele;
    }
    if (wizSim(texto)) {
      F.kill();
      return WIZ_META[sw.para].start(sw.texto);
    }
    return 'Continuando de onde paramos. ' + (F.Q[f.step] || '');
  }
  // troca de fluxo tem prioridade sobre confirmação pendente (evita "sim" acidental)
  const tr0 = wizDetectTroca(texto, flowKey);
  if (tr0 && !F.livres.includes(f.step)) {
    wizSwitch = { para: tr0, texto };
    return `Você está no meio do cadastro ${F.fluxo}. Quer largar e ${WIZ_TROCA_LABEL[tr0]}? (sim/não)`;
  }
  const cf = await wizVerConfirm(F, texto);
  if (cf) return cf;
  if (wizQuerVoltar(texto)) return wizVoltar(F);
  if (wizQuerAjuda(texto))
    return (
      WIZ_HELP[flowKey] +
      '\nDiga "voltar" pra corrigir, "pular" onde permitido, ou "cancelar" pra sair.\n' +
      (F.Q[f.step] || '')
    );
  // Uma pergunta sobre a lista é respondida com a LISTA.
  //
  // Fica antes do `wizDetectTroca` porque é mais especifica: enquanto o
  // fluxo continua a ser o de sempre, quem perguntou "qual talhão temos"
  // quer a lista de talhões — não quer ser interview sobre trocar de
  // cadastro. E "não tenho talhão" NÃO entra aqui: é resposta, e a
  // resposta é seguir sem talhão (passa, e o passo trata).
  //
  // A EXCEÇÃO é o prefill. Quem escreveu "cadastrar uma safra de
  // abobrinha" e depois perguntou "quais culturas vocês têm?" já disse a
  // cultura — está escrita na frase que abriu o cadastro. Barrar aqui
  // desperdiçaria a frase e obrigaria a pessoa a repetir o que já
  // disse. `_textoInicial`/`_tentouPre` é a mesma convenção que os
  // passos já usam para o prefill, e por isso é aqui que se lê.
  const passoLista = WIZ_PASSOS_LISTA[flowKey + ':' + f.step];
  const temPrefill = !!(f._textoInicial && !f._tentouPre);
  if (passoLista && !temPrefill && !wizDispensavel(texto) && wizEhPergunta(texto)) {
    const lista = await wizList(passoLista.url);
    // Se a frase APONTA para um nome da lista, é resposta — deixa passar.
    if (!wizEscolher(lista, texto).tal) {
      const r = wizComPergunta(passoLista.oQue, lista, passoLista.pergunta, passoLista.pular);
      if (r) return r;
    }
  }
  const tr = wizDetectTroca(texto, flowKey);
  if (tr && !F.livres.includes(f.step)) {
    wizSwitch = { para: tr, texto };
    return `Você está no meio do cadastro ${F.fluxo}. Quer largar e ${WIZ_TROCA_LABEL[tr]}? (sim/não)`;
  }
  return null;
}
async function wizPropId(w) {
  if (w.talhao && w.talhao.propriedade) return w.talhao.propriedade;
  if (window._iaPropPadrao) return window._iaPropPadrao;
  try {
    const j = await apiFetch('/api/propriedades/');
    const list = j.results || [];
    if (list.length) {
      window._iaPropPadrao = list[0].id;
      return list[0].id;
    }
  } catch {}
  return null;
}
async function wizRegistro(w) {
  if (w.registroId) return w.registroId;
  try {
    const j = await apiFetch(
      '/api/registros-producao/?search=' + encodeURIComponent(w.cultura.nome)
    );
    const list = j.results || j || [];
    const hit = (Array.isArray(list) ? list : []).find(
      (r) => r.cultura === w.cultura.id || wizNorm(r.nome).includes(wizNorm(w.cultura.nome))
    );
    if (hit) {
      w.registroId = hit.id;
      return hit.id;
    }
  } catch {}
  try {
    // ATENÇÃO: o endpoint espera name/cultureId/groupId (não nome/cultura/grupo)
    const created = await apiFetch('/api/registros-producao/', {
      method: 'POST',
      body: JSON.stringify({
        name: w.nome || 'Safra ' + w.cultura.nome,
        cultureId: w.cultura.id,
        groupId: w.cultura.grupo || 'vegetal',
      }),
    });
    w.registroId = created.id;
    return created.id;
  } catch {
    return null;
  }
}
function wizNavegarCultura(w) {
  try {
    if (typeof window.safeShowCulturaDetail === 'function' && w.cultura) {
      window.safeShowCulturaDetail(w.cultura.id, w.cultura.nome, w.cultura.grupo || 'vegetal');
    } else if (typeof window.showCulturaDetail === 'function' && w.cultura) {
      window.showCulturaDetail(w.cultura.id, w.cultura.nome, w.cultura.grupo || 'vegetal');
    }
  } catch {}
}

/* Constrói a lista de campos no formato do servidor (para IaColeta.desenha).
 *
 * O wizard local e o servidor têm de mostrar a MESMA lista — senão o produtor
 * vê coisas diferentes conforme o caminho. O formato e':
 *   { n, campo, rotulo, estado: 'preenchido'|'a_pedir', valor } */
function wizSafraColeta(w) {
  return [
    {
      n: 1,
      campo: 'cultura',
      rotulo: 'Cultura',
      estado: w.cultura ? 'preenchido' : 'a_pedir',
      valor: w.cultura ? w.cultura.nome : null,
    },
    {
      n: 2,
      campo: 'nome',
      rotulo: 'Nome da safra',
      estado: w.nome ? 'preenchido' : 'a_pedir',
      valor: w.nome || null,
    },
    {
      n: 3,
      campo: 'talhao',
      rotulo: 'Talhão/Zona',
      estado: w.talhao ? 'preenchido' : 'a_pedir',
      valor: w.talhao ? w.talhao.nome : null,
    },
    {
      n: 4,
      campo: 'ano',
      rotulo: 'Ano',
      estado: w.ano ? 'preenchido' : 'a_pedir',
      valor: w.ano || null,
    },
    {
      n: 5,
      campo: 'area_plantada',
      rotulo: 'Área plantada',
      estado: w.area ? 'preenchido' : 'a_pedir',
      valor: w.area ? w.area + ' ha' : null,
    },
  ];
}

function wizSafraStart(texto) {
  wizSafra = {
    step: 'cultura',
    cultura: null,
    nome: null,
    talhao: null,
    ano: null,
    area: null,
    safra: null,
    _textoInicial: texto || '',
    _tentouPre: false,
    anoPre: null,
  };
  const t4 = String(texto || '').match(/(\d{4})/);
  if (t4 && +t4[1] >= 1900 && +t4[1] <= 2101) wizSafra.anoPre = +t4[1];
  if (!wizSafra.anoPre) {
    const b = String(texto || '').match(/(\d{2})\/(\d{2,4})/);
    if (b) wizSafra.anoPre = +(b[2].length === 2 ? '20' + b[2] : b[2]);
  }
  window._sbColeta = wizSafraColeta(wizSafra);
  return 'Vamos cadastrar uma safra! 🌾\n[ ] Cultura\n[ ] Nome da safra\n[ ] Talhão/Zona\n[ ] Ano\n[ ] Área plantada\n\nQual a cultura?';
}
async function wizSafraStep(texto) {
  const w = wizSafra;
  const t = (texto || '').trim();
  if (wizCancelar(t)) {
    wizSafra = null;
    window._sbColeta = null;
    return 'Fluxo cancelado. Quando quiser, é só dizer "cadastrar nova safra".';
  }
  const _g = await wizGuardas(WIZ_META.safra, 'safra', texto);
  if (_g) return _g;
  /* A lista reflete o que JÁ foi preenchido — o passo actual é o que está
   * 'a_pedir'. Atualizar aqui garante que a lista aparece logo no turno
   * seguinte, sem esperar o servidor. */
  window._sbColeta = wizSafraColeta(w);
  /* ── pergunta cultura (com prefill da frase-gatilho) ── */
  if (w.step === 'cultura') {
    if (!w._tentouPre && w._textoInicial) {
      w._tentouPre = true;
      try {
        const hit0 = await wizPrefillCultura(w._textoInicial);
        if (hit0) {
          w.cultura = hit0;
          w.step = 'nome';
          wizNavegarCultura(w);
          let extra = '';
          if (w.cultura.ciclo_dias) extra += ` (ciclo ~${w.cultura.ciclo_dias} dias)`;
          return `${wizChecklist(w)}\n\nEntendi: ${
            w.cultura.nome
          }${extra}! Qual o nome da safra? (ex: Safra ${w.cultura.nome} ${
            w.anoPre || new Date().getFullYear()
          })`;
        }
      } catch {}
    }
    if (!t) {
      const todas = await wizList('/api/culturas/?dedupe=1');
      const nomes = todas
        .slice(0, 8)
        .map((c) => c.nome)
        .join(', ');
      return `Qual a cultura? (ex: ${nomes || 'café, milho, soja'})`;
    }
    const hits = await wizBuscarCultura(t);
    if (!hits.length) {
      const todas = await wizList('/api/culturas/?dedupe=1');
      const porPergunta = wizEhPergunta(t)
        ? wizComPergunta('essa cultura', todas, 'Qual a cultura?', 'cultura')
        : null;
      return porPergunta || wizSemAcerto('essa cultura', todas, t, 'cultura');
    }
    if (hits.length > 1) {
      return `Achei ${hits.length}: ${hits
        .slice(0, 5)
        .map((c) => c.nome)
        .join(', ')}. Qual delas?`;
    }
    w.cultura = hits[0];
    w.step = 'nome';
    wizNavegarCultura(w);
    let extra = '';
    if (w.cultura.ciclo_dias) extra += ` (ciclo ~${w.cultura.ciclo_dias} dias)`;
    return `${wizChecklist(w)}\n\nCultura: ${
      w.cultura.nome
    }${extra} — abri a guia dela. Qual o nome da safra? (ex: Safra ${
      w.cultura.nome
    } ${new Date().getFullYear()})`;
  }
  /* ── pergunta nome ── */
  if (w.step === 'nome') {
    if (!t) return 'Me diga o nome da safra para continuar.';
    // Uma pergunta pelo nome é uma pergunta — e a RESPOSTA a um
    // "como vocês chamam isso?" é uma sugestão. Sem esta porta, a
    // pergunta era gravada como nome da safra, e a safra ficava
    // cadastrada com o nome "qual nome vc sugere".
    if (wizEhPergunta(t)) {
      const sug = `Safra ${w.cultura.nome} ${new Date().getFullYear()}`;
      return `Um nome comum seria "${sug}". Quer esse, ou prefere outro?`;
    }
    if (wizSim(t) || wizNao(t) || /pular/.test(wizNorm(t))) {
      const sug = `Safra ${w.cultura.nome} ${new Date().getFullYear()}`;
      return wizArmarConfirm(
        WIZ_META.safra,
        `Que tal "${sug}"? (sim — ou diga outro nome)`,
        async () => {
          w.nome = sug;
          w.step = 'talhao';
          return `${wizChecklist(w)}\n\nQual o talhão/zona?`;
        },
        'Então me diga o nome da safra.'
      );
    }
    // A nossa pergunta não é o nome da safra. Sem esta guarda,
    // "como vocês chamam essa safra?" grava-se como nome e o POST vai com
    // ele — e um nome de safra errado propaga-se a aplicações, custo/ha e
    // rastreabilidade. Mesmo padrão de `talhao:nome` e `func:nome`.
    if (wizNaoEhValor(t))
      return `${wizChecklist(w)}\n\nQual o nome da safra? (ex: Safra ${w.cultura.nome} ${w.anoPre || new Date().getFullYear()})`;
    w.nome = t;
    w.step = 'talhao';
    return `${wizChecklist(w)}\n\nQual o talhão/zona?`;
  }
  /* ── pergunta talhão (opcional — aceita pular) ── */
  if (w.step === 'talhao') {
    // `wizDispensavel` em vez do regex à mão: a lista de "não tenho" é
    // a mesma que os outros passos usam, e "não tenho" contém "tem" —
    // que é palavra de pergunta. Se a pergunta for testada antes do
    // "não tenho", "não tenho talhão" deixa de ser resposta.
    if (!t || wizDispensavel(t)) {
      w.talhao = null;
      w.step = 'ano';
      return `${wizChecklist(
        w
      )}\n\nSem talhão, tudo bem — dá pra ligar depois.\nQual o ano da safra? (Enter = ${new Date().getFullYear()})`;
    }
    const list = await wizList('/api/talhoes/');
    const r = wizEscolher(list, t);
    if (r.alternativa.length) {
      return `Achei ${r.alternativa.length}: ${wizNomes(r.alternativa, 5).join(', ')}. Qual deles?`;
    }
    if (!r.tal) {
      // A pergunta que um produtor fez de facto — "qual talhão temos
      // disponível para plantar" — é respondida com a lista e com a
      // saída. Nunca com "não achei talhão <a pergunta inteira>".
      const porPergunta = wizEhPergunta(t)
        ? wizComPergunta('esse talhão', list, 'Qual o talhão/zona?', 'talhão')
        : null;
      if (porPergunta) return porPergunta;
      // Se já perguntou antes e o usuário não escolheu, oferece ações claras
      if (w._talhaoRetryCount === undefined) w._talhaoRetryCount = 0;
      w._talhaoRetryCount++;
      if (w._talhaoRetryCount >= 2) {
        w.talhao = null;
        w.step = 'ano';
        return `${wizChecklist(w)}\n\nSem problema — vou seguir sem talhão por agora. Você pode cadastrar um depois.\nQual o ano da safra? (Enter = ${new Date().getFullYear()})`;
      }
      return wizSemAcerto('esse talhão', list, t, 'talhão');
    }
    w.talhao = r.tal;
    w.step = 'ano';
    const sugArea = w.talhao.area_hectare ? ` (talhão tem ${w.talhao.area_hectare} ha)` : '';
    return `${wizChecklist(
      w
    )}\n\nQual o ano da safra? (Enter = ${new Date().getFullYear()})${sugArea}`;
  }
  /* ── pergunta ano (com prefill da frase-gatilho) ── */
  if (w.step === 'ano') {
    if (w.anoPre) {
      w.ano = w.anoPre;
      w.anoPre = null;
      w.step = 'area';
      const sug =
        w.talhao && w.talhao.area_hectare ? ` (Enter = ${w.talhao.area_hectare} ha do talhão)` : '';
      return `${wizChecklist(w)}\n\nAno ${
        w.ano
      } (entendi da sua frase — diga "voltar" se quiser mudar).\nQual a área plantada em ha?${sug}`;
    }
    // A pergunta NAO é o ano. `wizParseNum` tira o PRIMEIRO número do texto,
    // e uma pergunta sobre anos traz números: "a safra de 2019 foi a melhor,
    // qual o ano?" gravava 2019 e AVANÇAVA. A frase é plausível — é o que
    // alguém diz a meio de uma conversa — e o produtor via "Qual o ano da
    // safra?" a seguir, já com o ano errado no checklist.
    //
    // A guarda fica ANTES do `wizParseNum` por uma razão: depois de
    // extrair o número já não há forma de saber que ele veio de uma
    // pergunta. MEDIDO, 2026-10-04, `tests/sondas/sonda10_wizard.cjs` §D.
    if (wizEhPergunta(t)) {
      return `Qual o ano da safra? (ex: ${new Date().getFullYear()})`;
    }
    if (!t) {
      // `Safra.ano` e' `IntegerField()` sem `null=True` (app/models/safra.py:52),
      // logo o ano e' obrigatorio. O Enter assume o ano corrente — e o
      // convite DIZ que assume, que e' o que separa isto do `wizHoje()`
      // silencioso de `func:admissao`. Ver a nota longa nessa passagem.
      w.ano = new Date().getFullYear();
    } else {
      const num = wizParseNum(t);
      if (!num || num < 1900 || num > 2101) {
        return `Ano inválido — me diga um ano entre 1900 e 2100 (ou Enter = ${new Date().getFullYear()}).`;
      }
      w.ano = Math.round(num);
    }
    w.step = 'area';
    const sug =
      w.talhao && w.talhao.area_hectare ? ` (Enter = ${w.talhao.area_hectare} ha do talhão)` : '';
    return `${wizChecklist(w)}\n\nQual a área plantada em ha?${sug}`;
  }
  /* ── pergunta área + CRIA (com trava de absurdo e duplicada) ── */
  if (w.step === 'area') {
    let num = wizParseNum(t);
    if (!num && w.talhao && w.talhao.area_hectare) num = parseFloat(w.talhao.area_hectare);
    if (!num || num <= 0)
      return 'Preciso da área plantada em ha (ex: 12,5 — pode escrever "doze e meio"). Qual a área?';
    const criar = async () => {
      w.area = num;
      const propId = await wizPropId(w);
      try {
        const payload = {
          safra_nome: w.nome,
          cultura: w.cultura.id,
          ano: w.ano,
          area_plantada: w.area,
          propriedade: propId,
        };
        if (w.talhao) payload.talhao = w.talhao.id;
        const created = await apiFetch('/api/safras/', {
          method: 'POST',
          body: JSON.stringify(payload),
        });
        w.safra = created;
        w.step = 'datas_p';
        return `${wizChecklist(w)}\n\nPronto, cadastro feito! ✅ Safra "${w.nome}" criada (id ${
          created.id
        }).\nQual a data do plantio? (Enter = pular)`;
      } catch (e) {
        return `Não consegui criar a safra: ${e.message}. Confira os dados — qual a área plantada?`;
      }
    };
    const limiteTalhao =
      w.talhao && w.talhao.area_hectare ? parseFloat(w.talhao.area_hectare) * 3 : 10000;
    if (num > Math.max(limiteTalhao, 10000)) {
      return wizArmarConfirm(
        WIZ_META.safra,
        `⚠️ ${num} ha é uma área bem grande — confirma que é isso mesmo? (sim/não)`,
        criar,
        'Ok, qual a área correta em ha?'
      );
    }
    try {
      const todas = await wizList('/api/safras/');
      const dup = todas.find(
        (s) => wizNorm(s.safra_nome) === wizNorm(w.nome) && Number(s.ano) === Number(w.ano)
      );
      if (dup) {
        return wizArmarConfirm(
          WIZ_META.safra,
          `⚠️ Já existe "${w.nome}" em ${w.ano} (id ${dup.id}). Criar outra mesmo assim? (sim/não)`,
          criar,
          'Ok — me diga outro nome pra safra (diga "voltar" pra corrigir o nome).'
        );
      }
    } catch {}
    return await criar();
  }
  /* ── vegetal: data do plantio (opcional) ── */
  if (w.step === 'datas_p') {
    const n = wizNorm(t);
    if (!t || /pular|nao sei|depois/.test(n)) {
      w.step = 'ramo';
      return 'Sem datas, tudo bem!\nVamos continuar para o ciclo produtivo ou IoT?';
    }
    const d = wizParseDatas(t);
    if (!d.length)
      return 'Qual a data do plantio? (ex: 15/10/2025, "15 de outubro", "ontem" — ou Enter para pular)';
    try {
      await apiFetch(`/api/safras/${w.safra.id}/`, {
        method: 'PATCH',
        body: JSON.stringify({ data_plantio: d[0] }),
      });
      w.plantioIso = d[0];
      w.step = 'datas_c';
      return `Plantio anotado: ${wizFmtData(d[0])}! 🌱\nE a previsão de colheita? (Enter = pular)`;
    } catch (e) {
      w.step = 'datas_c';
      return `Não consegui salvar o plantio: ${e.message}. E a previsão de colheita? (Enter = pular)`;
    }
  }
  /* ── vegetal: previsão de colheita (opcional, com trava de inversão) ── */
  if (w.step === 'datas_c') {
    const n = wizNorm(t);
    if (!t || /pular|nao sei|depois/.test(n)) {
      w.step = 'ramo';
      return 'Fechado!\nVamos continuar para o ciclo produtivo ou IoT?';
    }
    const d = wizParseDatas(t);
    if (!d.length)
      return 'Qual a previsão de colheita? (ex: 20/02/2026, "fevereiro", "mês que vem" — ou Enter para pular)';
    const salvar = async () => {
      try {
        await apiFetch(`/api/safras/${w.safra.id}/`, {
          method: 'PATCH',
          body: JSON.stringify({ data_colheita: d[0] }),
        });
      } catch (e) {
        return `Não consegui salvar a colheita: ${e.message}. Vamos continuar para o ciclo produtivo ou IoT?`;
      }
      w.step = 'ramo';
      return `Colheita prevista: ${wizFmtData(
        d[0]
      )}! 🌾\nVamos continuar para o ciclo produtivo ou IoT?`;
    };
    if (w.plantioIso && d[0] < w.plantioIso) {
      return wizArmarConfirm(
        WIZ_META.safra,
        `⚠️ ${wizFmtData(d[0])} é ANTES do plantio (${wizFmtData(
          w.plantioIso
        )}). Confirma mesmo assim? (sim/não)`,
        salvar,
        'Ok, qual a previsão de colheita correta?'
      );
    }
    return await salvar();
  }
  /* ── ramo: ciclo ou iot (com rotas cruzadas e saidas) ── */
  if (w.step === 'ramo') {
    const n = wizNorm(t);
    if (wizAquaTrigger(t)) {
      wizSafra = null;
      return wizAquaStart();
    }
    if (wizAnimalTrigger(t)) {
      wizSafra = null;
      return wizAnimalStart();
    }
    if (typeof wizTalhaoTrigger === 'function' && wizTalhaoTrigger(t)) {
      wizSafra = null;
      return wizTalhaoStart(t);
    }
    if (typeof wizFuncRemTrigger === 'function' && wizFuncRemTrigger(t)) {
      wizSafra = null;
      return wizFuncRemStart(t);
    }
    if (typeof wizFuncTrigger === 'function' && wizFuncTrigger(t)) {
      wizSafra = null;
      return wizFuncStart(t);
    }
    if (typeof wizTarefaTrigger === 'function' && wizTarefaTrigger(t)) {
      wizSafra = null;
      return wizTarefaStart(t);
    }
    if (wizSim(t)) return 'Diga um dos dois: ciclo produtivo ou IoT?';
    if (wizNao(t)) {
      w.step = 'pos';
      return 'Fechado! ✅ O que mais? (novo estágio, IoT, ou outra coisa)';
    }
    if (/ciclo|produtiv|estagio|estágio|fase/.test(n)) {
      w.step = 'ciclo_nome';
      const reg = await wizRegistro(w);
      if (!reg)
        return 'Não consegui ligar os estágios (sem registro da cultura). Abra a guia da cultura primeiro e tente de novo — ou vamos para IoT?';
      return 'Agora vamos cadastrar um ciclo produtivo. Qual o nome do primeiro estágio? (ex: dormência, floração, enchimento de grãos)';
    }
    if (/iot|sensor|dispositiv|estacao|estação|umidade|ph/.test(n)) {
      w.step = 'iot_scan';
      return await wizIotScan(w);
    }
    return 'Vamos continuar para o ciclo produtivo ou IoT?';
  }
  /* ── ciclo: nome do estágio ── */
  if (w.step === 'ciclo_nome') {
    if (!t) return 'Qual o nome do estágio? (ex: dormência)';
    // `wizEhPergunta`: uma pergunta ("como se chama a dormencia?") nao e' um
    // nome de estagio, e sem esta guarda era gravada como `nome` no
    // `/api/estagios-cultura/`. Mesmo padrao dos outros wizards.
    if (wizSim(t) || wizNao(t) || wizNaoEhValor(t))
      return 'Preciso do nome do estágio (ex: dormência, floração) — ou diga "pular" pra voltar.';
    if (/pular|sair|sem estagio/.test(wizNorm(t))) {
      w.step = 'ramo';
      return 'Sem estágio, tudo bem.\nVamos continuar para o ciclo produtivo ou IoT?';
    }
    const reg = await wizRegistro(w);
    try {
      const ordem = (w.estagios || 0) + 1;
      const created = await apiFetch('/api/estagios-cultura/', {
        method: 'POST',
        body: JSON.stringify({ registro: reg, nome: t, ordem }),
      });
      w.estagio = created;
      w.estagios = ordem;
      w.step = 'ciclo_datas';
      return `Ok, ${t} cadastrada! ✅\nQuais são as datas de início e término do estágio? (ex: 12/09/2025 até 12/02/2026)`;
    } catch (e) {
      return `Não consegui criar o estágio: ${e.message}. Qual o nome do estágio?`;
    }
  }
  /* ── ciclo: datas (com trava de inversão) ── */
  if (w.step === 'ciclo_datas') {
    const datas = wizParseDatas(t);
    if (datas.length < 2)
      return 'Preciso das duas datas (ex: 12/09/2025 até 12/02/2026). Quais são?';
    if (datas[1] < datas[0]) {
      return `⚠️ O término (${wizFmtData(datas[1])}) ficou ANTES do início (${wizFmtData(
        datas[0]
      )}). Me diga de novo na ordem certa (início até término).`;
    }
    try {
      await apiFetch(`/api/estagios-cultura/${w.estagio.id}/`, {
        method: 'PATCH',
        body: JSON.stringify({ data_inicio: datas[0], data_fim: datas[1] }),
      });
      w.step = 'ciclo_tarefa_q';
      const [a, m, d] = datas[0].split('-');
      const [a2, m2, d2] = datas[1].split('-');
      return `Ok, datas cadastradas! ✅ ${a}/${m}/${d} até ${a2}/${m2}/${d2}.\nQuer associar tarefas desse estágio aos seus funcionários?`;
    } catch (e) {
      return `Não consegui salvar as datas: ${e.message}. Quais são as datas?`;
    }
  }
  /* ── ciclo: quer tarefas? ── */
  if (w.step === 'ciclo_tarefa_q') {
    if (wizSim(t)) {
      w.step = 'ciclo_tarefa';
      return 'Qual tarefa e para quem? (ex: associe a poda aos técnicos agrícolas)';
    }
    if (wizNao(t)) {
      w.step = 'pos';
      return 'Fechado! ✅ O que mais? (novo estágio, IoT, ou outra coisa)';
    }
    return 'Quer associar tarefas desse estágio aos seus funcionários? (sim/não)';
  }
  /* ── ciclo: cria tarefa ── */
  if (w.step === 'ciclo_tarefa') {
    if (!t || wizSim(t) || wizNao(t)) {
      return 'Qual tarefa e para quem? (ex: associe a poda aos técnicos agrícolas)';
    }
    return await wizCriarTarefa(w, t);
  }
  /* ── ciclo: mais tarefas? ── */
  if (w.step === 'ciclo_mais') {
    if (wizSim(t)) {
      w.step = 'ciclo_tarefa';
      return 'Qual a próxima tarefa e para quem?';
    }
    if (wizNao(t)) {
      w.step = 'pos';
      return 'Fechado! ✅ Quer cadastrar um novo estágio, ir para IoT ou outra coisa?';
    }
    return 'Quer cadastrar mais tarefas? (sim/não)';
  }
  /* ── iot: integrar? ── */
  if (w.step === 'iot_integrar') {
    const n = wizNorm(t);
    const querNova =
      /tambem|também|nova|novo|cadastrar|umidade|temperatura|pluvi|estacao|estação/.test(n);
    if (wizSim(t) || querNova) {
      if (w.dev && (!w.dev.talhao || w.dev.talhao !== w.talhao.id)) {
        try {
          await apiFetch(`/api/iot/devices/${w.dev.id}/`, {
            method: 'PATCH',
            body: JSON.stringify({ talhao: w.talhao.id }),
          });
        } catch {}
      }
      let msg = w.dev ? `Ok, ${w.dev.nome} integrado ao ${w.talhao.nome}! ✅` : 'Ok!';
      if (querNova) {
        return msg + '\n' + (await wizCriarEstacao(w, t));
      }
      w.step = 'iot_nova_q';
      return msg + '\nQuer cadastrar uma nova estação? (ex: umidade do solo e ambiente)';
    }
    if (wizNao(t)) {
      w.step = 'pos';
      return 'Fechado! ✅ O que mais? (ciclo produtivo ou outra coisa)';
    }
    return 'Quer que eu integre os dados dela a esta safra? (sim/não)';
  }
  /* ── iot: quer nova estação? ── */
  if (w.step === 'iot_nova_q') {
    if (wizSim(t)) {
      w.step = 'iot_nova';
      return 'Qual estação? (ex: umidade do solo e ambiente)';
    }
    w.step = 'pos';
    return 'Fechado! ✅ O que mais?';
  }
  /* ── iot: cria estação ── */
  if (w.step === 'iot_nova') {
    if (!t || wizNao(t)) {
      w.step = 'pos';
      return 'Fechado! ✅ O que mais?';
    }
    return await wizCriarEstacao(w, t);
  }
  /* ── pós-fluxo (com rotas cruzadas) ── */
  if (w.step === 'pos') {
    const n = wizNorm(t);
    if (wizAquaTrigger(t)) {
      wizSafra = null;
      return wizAquaStart();
    }
    if (wizAnimalTrigger(t)) {
      wizSafra = null;
      return wizAnimalStart();
    }
    if (typeof wizTalhaoTrigger === 'function' && wizTalhaoTrigger(t)) {
      wizSafra = null;
      return wizTalhaoStart(t);
    }
    if (typeof wizFuncRemTrigger === 'function' && wizFuncRemTrigger(t)) {
      wizSafra = null;
      return wizFuncRemStart(t);
    }
    if (typeof wizFuncTrigger === 'function' && wizFuncTrigger(t)) {
      wizSafra = null;
      return wizFuncStart(t);
    }
    if (typeof wizTarefaTrigger === 'function' && wizTarefaTrigger(t)) {
      wizSafra = null;
      return wizTarefaStart(t);
    }
    if (/novo estagio|nova etapa|novo estágio|estagio|estágio|ciclo/.test(n)) {
      w.step = 'ciclo_nome';
      return 'Qual o nome do novo estágio?';
    }
    if (/iot|sensor|estacao|estação|device/.test(n)) {
      w.step = 'iot_scan';
      return await wizIotScan(w);
    }
    if (/nova safra|outra safra|cadastrar/.test(n)) {
      return wizSafraStart(typeof t !== 'undefined' ? t : lastUser);
    }
    wizSafra = null;
    return 'Fechado! ✅ Se precisar, é só chamar: nova safra, ciclo ou IoT.';
  }
  wizSafra = null;
  return 'Vamos recomeçar: diga "cadastrar nova safra".';
}
async function wizIotScan(w) {
  if (!w.talhao) {
    w.dev = null;
    w.candidatos = [];
    w.step = 'iot_nova_q';
    return 'Sua safra não tem talhão ligado — não dá pra varrer sensores. Quer cadastrar uma estação direto? (ex: umidade do solo e ambiente)';
  }
  const all = await wizList('/api/iot/devices/');
  const noTalhao = all.filter(
    (d) =>
      d.talhao === w.talhao.id ||
      (d.talhao == null && d.propriedade === (w.talhao.propriedade || window._iaPropPadrao))
  );
  w.candidatos = noTalhao;
  w.step = 'iot_integrar';
  if (!noTalhao.length) {
    w.dev = null;
    w.step = 'iot_nova_q';
    return `Verifiquei o ${w.talhao.nome} e não achei nenhum dispositivo. Quer cadastrar uma estação? (ex: umidade do solo e ambiente)`;
  }
  w.dev = noTalhao[0];
  const tipo = w.dev.tipo ? ` de ${w.dev.tipo}` : '';
  const onde = w.dev.talhao === w.talhao.id ? ` no ${w.talhao.nome}` : ' (ainda sem talhão)';
  return `Verificando a existência de dispositivos… achei ${noTalhao.length}: ${w.dev.nome}${tipo}${onde}.\nQuer que eu integre os dados dela a esta safra?`;
}
async function wizCriarEstacao(w, t) {
  if (!w.talhao) {
    w.step = 'pos';
    return 'Sem talhão ligado não consigo posicionar a estação. O que mais? (ciclo produtivo ou outra coisa)';
  }
  const n = wizNorm(t);
  let tipo = 'umidade do solo e ambiente';
  if (/ph/.test(n)) tipo = 'pHmetro';
  else if (/pluvi|chuva/.test(n)) tipo = 'pluviômetro';
  else if (/temperatura/.test(n) && !/umidade/.test(n)) tipo = 'temperatura';
  else if (/umidade/.test(n)) tipo = 'umidade do solo e ambiente';
  const propId = await wizPropId(w);
  const eui = wizEui();
  const nome = `Estação ${tipo} — ${w.talhao.nome}`;
  try {
    await apiFetch('/api/iot/devices/', {
      method: 'POST',
      body: JSON.stringify({
        nome,
        device_eui: eui,
        tipo: 'sensor',
        protocolo: 'lora',
        propriedade: propId,
        talhao: w.talhao.id,
        ativo: true,
      }),
    });
    w.step = 'pos';
    const base = location.origin;
    return `Ok, ${tipo} cadastrado! ✅ Gerando API para a estação…\n\nPonto criado no sistema para receber os dados. Insira no dispositivo:\n• Endpoint: POST ${base}/api/iot/push/${eui}/\n• JSON: {"metric": "umidade_solo", "value": 62.5, "unit": "%"}\n\nEle já estará conectado e enviando no sistema. ✅ O que mais?`;
  } catch (e) {
    w.step = 'pos';
    return `Não consegui cadastrar a estação: ${e.message}. O que mais?`;
  }
}
async function wizCriarTarefa(w, t) {
  const n = wizNorm(t);
  /* "associe a tarefa de X aos Y" / "associe X aos Y" / "X para os Y" */
  let desc = t;
  let papel = '';
  const m =
    n.match(/tarefa de (.+?) (aos|para) (os |as )?(.+)/) ||
    n.match(/(.+?) (para|aos) (os |as )?(.+)/);
  if (m) {
    papel = (m[4] || '').trim();
    const raw = (m[1] || '').trim();
    const at = n.indexOf(raw);
    desc = at >= 0 ? t.substring(at, at + raw.length) : raw;
  }
  desc = desc
    .replace(
      /^(associe|associar|crie|criar|adiciona|adicionar|coloque|colocar|faz|fazer|cadastre|cadastrar)\s+/i,
      ''
    )
    .replace(/^(a|o|as|os)\s+/i, '')
    .replace(/^tarefa\s+(de\s+)?/i, '')
    .trim();
  if (!desc) desc = 'Tarefa do estágio';
  const funcs = await wizList('/api/funcionarios/');
  const GLUE = /^(aos|para|dos|das|do|da|de|os|as|ao|o|a|um|uma|nos|nas|no|na|e)$/;
  const keys = wizNorm(papel)
    .split(/\s+/)
    .filter((k) => k.length > 2 && !GLUE.test(k))
    .map((k) => (k.endsWith('s') && k.length > 4 ? k.slice(0, -1) : k));
  const alvos = papel
    ? funcs.filter((f) => {
        const c = wizNorm((f.cargo || '') + ' ' + (f.setor || '')).replace(/s\b/g, '');
        return keys.length > 0 && keys.some((k) => c.includes(k));
      })
    : [];
  const propId = await wizPropId(w);
  const criadas = [];
  const lista = alvos.slice(0, 5);
  if (lista.length) {
    for (const f of lista) {
      try {
        await apiFetch('/api/tarefas-estagio/', {
          method: 'POST',
          body: JSON.stringify({
            estagio: w.estagio.id,
            descricao: desc,
            funcionario: f.id,
            propriedade: propId,
          }),
        });
        criadas.push(f.nome);
      } catch {}
    }
  }
  if (!criadas.length) {
    try {
      await apiFetch('/api/tarefas-estagio/', {
        method: 'POST',
        body: JSON.stringify({
          estagio: w.estagio.id,
          descricao: desc,
          cargo_alvo: papel || 'equipe',
          propriedade: propId,
        }),
      });
      w.step = 'ciclo_mais';
      return `Ok, tarefa "${desc}" criada para ${
        papel || 'a equipe'
      }! ✅ (sem funcionário exato, ficou por cargo)\nQuer cadastrar mais tarefas?`;
    } catch (e) {
      w.step = 'ciclo_mais';
      return `Não consegui criar a tarefa: ${e.message}. Quer tentar outra?`;
    }
  }
  w.step = 'ciclo_mais';
  return `Ok feito! ✅ Tarefa "${desc}" associada a: ${criadas.join(
    ', '
  )}.\nQuer cadastrar mais tarefas?`;
}
function getChecklistHTML() {
  if (!iaCadastroPendente) return '';
  const { recurso, dados, esquema, etapa } = iaCadastroPendente;
  let html = `<div style="font-size:11px;color:#0f9d6e;font-weight:700;margin:6px 0 4px">📋 Cadastrando ${recurso} — ${etapa}/${esquema.length}</div>`;
  html += '<div style="display:flex;flex-direction:column;gap:3px">';
  esquema.forEach((campo, idx) => {
    const feito = idx < etapa;
    const atual = idx === etapa;
    const valor = dados[campo.campo] || '';
    const icon = feito ? '✅' : atual ? '⏳' : '⬜';
    const cor = feito ? '#0f9d6e' : atual ? '#d97706' : '#94a3b8';
    html += `<div style="font-size:11px;color:${cor};display:flex;justify-content:space-between"><span>${icon} ${
      campo.campo
    }</span><span style="opacity:.8">${valor || (atual ? '— atual' : '—')}</span></div>`;
  });
  html += '</div>';
  return html;
}
function iniciarCadastro(recurso) {
  const esquema = ESQUEMAS_CADASTRO[recurso];
  if (!esquema)
    return `Recurso ${recurso} ainda não tem wizard, mas posso criar direto. Me diga os dados.`;
  iaCadastroPendente = { recurso, dados: {}, etapa: 0, esquema };
  // preenche valores padrão
  esquema.forEach((c) => {
    if (c.valorPadrao && !c.obrigatorio) {
    }
  });
  const primeiro = esquema[0];
  const def = primeiro.valorPadrao ? ` (sugestão: ${primeiro.valorPadrao()})` : '';
  return `${primeiro.pergunta}${def}\n\n${getChecklistHTML()}`;
}
// ══════════════════════════════════════════════════════════════
// NLP WIZARD — extrai múltiplos campos de linguagem natural
// ══════════════════════════════════════════════════════════════
function extrairCamposNL(texto, esquema, etapaAtual) {
  const t = texto
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');
  const extraidos = {};
  let encontrou = 0;

  for (let i = etapaAtual; i < esquema.length; i++) {
    const campo = esquema[i];
    const nomeCampo = campo.campo.toLowerCase();
    let valor = null;

    // ── Padrões por nome de campo ──
    if (nomeCampo === 'nome') {
      const m = t.match(
        /(?:nome|chama|chamado)\s*(?:e|sera|do|da|del[ea])?\s*(?:e|:)?\s*(.+?)(?:\s*[,;.]\s|\s+(?:a\s+)?(?:area|com|e\s+a)\s|$)/i
      );
      if (m) valor = m[1].trim();
    }
    if (nomeCampo === 'area' || nomeCampo === 'area_total') {
      const m = t.match(
        /(?:area|com)\s*(?:e|sera|del[ea]|de|total)?\s*(?:e|:)?\s*([\d.,]+)\s*(?:ha|hectare|hec)/i
      );
      if (m) valor = m[1].replace(',', '.');
    }
    if (nomeCampo === 'cultura') {
      const m = t.match(
        /(?:cultura|plantar|plantio|plantando|plantar.)\s*(?:e|sera|de|do|da)?\s*(?:e|:)?\s*(.+?)(?:\s*[,;.]\s|$)/i
      );
      if (m) valor = m[1].trim();
      // fallback: se a frase menciona uma cultura comum no final
      if (!valor) {
        const culturas = [
          'soja',
          'milho',
          'cafe',
          'arroz',
          'algodao',
          'feijao',
          'trigo',
          'cana',
          'cacau',
          'sorgo',
          'mandioca',
        ];
        for (const c of culturas) {
          if (t.includes(c) && !t.match(new RegExp('nome.*' + c))) {
            valor = c.charAt(0).toUpperCase() + c.slice(1);
            break;
          }
        }
      }
    }
    if (nomeCampo === 'municipio' || nomeCampo === 'cidade') {
      const m = t.match(
        /(?:municipio|cidade|localidade|para|em)\s*(?:e|sera|de|do|da)?\s*(?:e|:)?\s*(.+?)(?:\s*[,;.]\s|$)/i
      );
      if (m) valor = m[1].trim();
    }
    if (nomeCampo === 'latitude' || nomeCampo === 'lat') {
      const m = t.match(/(?:latitude|lat)\s*(?:e|:)?\s*(-?[\d.,]+)/i);
      if (m) valor = m[1].replace(',', '.');
    }
    if (nomeCampo === 'longitude' || nomeCampo === 'lon' || nomeCampo === 'lng') {
      const m = t.match(/(?:longitude|lon|lng)\s*(?:e|:)?\s*(-?[\d.,]+)/i);
      if (m) valor = m[1].replace(',', '.');
    }
    if (nomeCampo === 'cargo') {
      const cargos = [
        'tratorista',
        'operador_pulverizador',
        'vaqueiro',
        'gerente',
        'aux_campo',
        'motorista',
        'mecanico_agricola',
      ];
      for (const c of cargos) {
        if (t.includes(c.replace(/_/g, ' ')) || t.includes(c)) {
          valor = c.toUpperCase();
          break;
        }
      }
      if (!valor && t.includes('operador')) valor = 'OPERADOR_PULVERIZADOR';
      if (!valor && t.includes('auxiliar')) valor = 'AUX_CAMPO';
      if (!valor && t.includes('mecanico')) valor = 'MECANICO_AGRICOLA';
    }
    if (nomeCampo === 'salario') {
      const m = t.match(/(?:salario|sal.)\s*(?:e|sera|de)?\s*(?:r\$)?\s*([\d.,]+)/i);
      if (m) valor = m[1].replace(/\./g, '').replace(',', '.');
    }
    if (nomeCampo === 'quantidade') {
      const m = t.match(/(?:quantidade|qtd|qtde)\s*(?:e|:)?\s*([\d.,]+)/i);
      if (m) valor = m[1].replace(',', '.');
    }
    if (nomeCampo === 'telefone') {
      const m = t.match(/(\(?\d{2}\)?\s*\d{4,5}[\s.-]?\d{4})/);
      if (m) valor = m[1];
    }
    if (nomeCampo === 'titulo') {
      const m = t.match(/(?:tarefa|titulo|titulo.)\s*(?:e|sera|:)?\s*(.+?)(?:\s*[,;.]\s|$)/i);
      if (m) valor = m[1].trim();
    }

    if (valor && valor.length > 0 && valor.length < 200) {
      extraidos[campo.campo] = valor;
      encontrou++;
    }
  }
  return encontrou >= 2 ? extraidos : null;
}

function limparValorNumerico(valor) {
  if (!valor || typeof valor !== 'string') return valor;
  // Remove unidades comuns: "2 hectares" → "2", "3500 reais" → "3500"
  let v = valor.trim();
  v = v
    .replace(
      /\s*(hectares?|ha|metros?|m²|m2|kg|kilos?|quilos?|toneladas?|ton|litros?|l|sacas?|sc|unidades?|un|reais|r\$|dias?)\s*$/i,
      ''
    )
    .trim();
  v = v.replace(',', '.');
  // Se sobrou algo que parece número, retorna
  if (v.match(/^-?[\d.]+$/)) return v;
  return valor.trim();
}

/* Os recursos cujo cadastro vai para uma FAZENDA, e por isso precisam do id
 * dela. `EstacaoMeteo.propriedade` é `ForeignKey` obrigatória: sem isto o
 * POST vai sem dono e o servidor responde 400 no fim de uma conversa
 * inteira.
 *
 * Vive numa lista, e não repetido em dois sítios, porque foi essa repetição
 * que deixou `estacoes` de fora — os dois blocos diziam a mesma coisa, e só
 * um deles se lembrava do quarto recurso. */
const RECURSOS_COM_PROPRIEDADE = ['funcionarios', 'talhoes', 'operacoes', 'estacoes'];

function avancarCadastro(resposta) {
  if (!iaCadastroPendente) return null;
  const t = resposta.toLowerCase().trim();
  if (t === 'cancelar' || t === 'sair' || t === 'parar' || t === 'cancela') {
    iaCadastroPendente = null;
    return '❌ Cadastro cancelado.';
  }
  const { esquema, etapa, dados, recurso } = iaCadastroPendente;
  const campoAtual = esquema[etapa];
  if (!campoAtual) return null;

  // ── NLP: tenta extrair múltiplos campos de uma frase longa ──
  if (resposta.length > 15 && etapa < esquema.length - 1) {
    const extraidos = extrairCamposNL(resposta, esquema, etapa);
    if (extraidos) {
      // Preenche todos os campos extraídos
      for (const [campo, valor] of Object.entries(extraidos)) {
        const sch = esquema.find((s) => s.campo === campo);
        dados[campo] = sch?.tipo === 'number' ? limparValorNumerico(valor) : valor;
      }
      // Avança para o primeiro campo não preenchido
      let novaEtapa = esquema.length;
      for (let i = 0; i < esquema.length; i++) {
        if (!dados[esquema[i].campo] && esquema[i].obrigatorio) {
          novaEtapa = i;
          break;
        }
      }
      iaCadastroPendente.etapa = novaEtapa;
      if (novaEtapa >= esquema.length) {
        // Todos preenchidos → finalizar
        const dadosFinais = { ...dados };
        if (RECURSOS_COM_PROPRIEDADE.includes(recurso) && !dadosFinais.propriedade)
          if (window._iaPropPadrao)
            /* Propriedade padrão do usuário (nunca id fixo — varia por conta) */
            dadosFinais.propriedade = window._iaPropPadrao;
        Object.keys(dadosFinais).forEach((k) => {
          if (dadosFinais[k] === 'pular') delete dadosFinais[k];
        });
        iaCadastroPendente = null;
        return { finalizar: true, recurso, dados: { ...dadosFinais } };
      }
      const proximo = esquema[novaEtapa];
      const resumo = Object.entries(dados)
        .filter(([, v]) => v)
        .map(([k, v]) => `✅ ${k}: ${v}`)
        .join('\n');
      return `Entendi! Preenchi automaticamente:\n${resumo}\n\nFalta: ${
        proximo.pergunta
      }\n\n${getChecklistHTML()}`;
    }
  }

  // ── Preenchimento campo a campo (original) ──
  if (t === 'pular') {
    // "pular" num campo OBRIGATÓRIO não é pular: gravava a palavra como
    // coordenada ("pular" em `latitude`) e o servidor devolvia 400. Ou o
    // produtor escreve o valor, ou o cadastro não fecha — e diz-se qual das
    // duas coisas está a acontecer.
    if (campoAtual.obrigatorio) return `Este campo é obrigatório: ${campoAtual.pergunta}`;
    // pula
  } else {
    if (campoAtual.obrigatorio && !resposta.trim())
      return `Esse campo é obrigatório. ${campoAtual.pergunta}`;
    let valor = resposta.trim();
    if (campoAtual.tipo === 'number') valor = limparValorNumerico(valor);
    dados[campoAtual.campo] = valor;
  }
  iaCadastroPendente.etapa += 1;
  if (iaCadastroPendente.etapa >= esquema.length) {
    const dadosFinais = { ...dados };
    if (RECURSOS_COM_PROPRIEDADE.includes(recurso) && !dadosFinais.propriedade)
      if (window._iaPropPadrao)
        /* Propriedade padrão do usuário (nunca id fixo — varia por conta) */
        dadosFinais.propriedade = window._iaPropPadrao;
    Object.keys(dadosFinais).forEach((k) => {
      if (dadosFinais[k] === 'pular') delete dadosFinais[k];
    });
    iaCadastroPendente = null;
    return { finalizar: true, recurso, dados: { ...dadosFinais } };
  }
  const proximo = esquema[iaCadastroPendente.etapa];
  const def = proximo.valorPadrao ? ` (sugestão: ${proximo.valorPadrao()})` : '';
  const placeholder = proximo.placeholder ? ` Ex: ${proximo.placeholder}` : '';
  return `${proximo.pergunta}${def}${placeholder}\n\n${getChecklistHTML()}`;
}

/* IA_SYSTEM — a persona, e SÓ a persona.
 *
 * ANTES, este bloco trazia uma lista de ferramentas escrita à mão: `navegar`,
 * `consultar`, `criar`, `iniciar_cadastro`, `irrigacao`, `atualizar`,
 * `excluir`, `relatorio`, `buscar_web`, mais quatro de compatibilidade.
 * Treze nomes.
 *
 * MEDIDO: as TREZE eram fantasmas. Nenhuma existe no catálogo das 76. E as 76
 * verdadeiras não estavam em lado nenhum do prompt.
 *
 * A consequência, medida ponta a ponta por HTTP, era que TODA a tool call que
 * este modelo conseguia escrever voltava `tool_fora_do_catalogo`. Não era uma
 * ferramenta que às vezes falhava — era a ponte inteira entre o modelo e as
 * mãos cortada. (FILA #27.)
 *
 * A lista das ferramentas NÃO volta aqui. Ela vem do servidor, em
 * `vocabularioAmplia()`, e é derivada do catálogo a cada pedido. Uma lista
 * escrita à mão é uma lista para se esquecer de acrescentar — e esta foi a
 * que custou um turno inteiro de chamadas inúteis.
 *
 * Se o servidor não responder, o prompt diz que não sabe os nomes. Dizer
 * "não sei" ao modelo é a única coisa honesta; inventar os nomes é
 * exactamente o defeito.
 */
const IA_SYSTEM = `Você é a AmplIA, assistente inteligente do Ampliagro.
Ajude o usuário a operar TODO o sistema com autonomia total: consultar, criar, atualizar e excluir qualquer cadastro, navegar entre telas, gerar relatórios, automatizar tarefas e migrar dados.

ESTILO: respostas curtas, profissionais, em PT-BR (1-2 frases). Se precisar agir, responda APENAS com JSON da tool, no formato {"tool":"amplia_<nome>","args":{...}}, e nada mais.

REGRAS:
- As ferramentas disponíveis estão listadas abaixo, com o nome EXATO. Copie o nome tal e qual; não o traduza, não o abrevie, não o complete.
- Um nome que não está na lista NÃO EXISTE. Se nenhuma servir, diga o que não consegue fazer — não invente um nome.
- Uma ferramenta de ESCRITA muda dados: o servidor vai pedir confirmação ao produtor. Não chame uma sem o produtor ter pedido.
- Priorize ação sobre explicação. Se o usuário disser "criar", "abrir", "mostrar", use a ferramenta sem perguntar.
- Para CADASTROS com falta de dados, a ferramenta devolve uma pergunta: responda chamando a MESMA ferramenta outra vez, com o campo que ela pediu preenchido.
- IMPORTANTE — quando o painel desenhou uma LISTA de campos (ele mostra "1 … 2 … 3 …"), NÃO escreva os nomes dos campos na sua resposta. A lista já está no ecrã. Escreva no máximo uma frase curta, ou nada. Escrever "Cultura, Nome da safra, Talhão, Ano" é repetir o que o produtor está a ver, e faz a tela descer.
- Privacidade total: nunca exponha dados sensíveis em buscas externas.
- Entenda o sistema do usuário (propriedades, talhões, safras) via contexto injetado.
`;

/* O vocabulário que o modelo recebe, e de onde vem.
 *
 * `/api/amplia/vocabulario/` devolve os 76 nomes verdadeiros em ~2 500
 * caracteres (~630 tokens). O catálogo completo (`/api/amplia/tools/`) são
 * ~8 700 tokens, e este modelo tem janela de 4 096 — não cabia, e nem
 * cabendo, 78 schemas atravessam um modelo que já leva contexto e histórico.
 *
 * Cache de 10 minutos, como o catálogo de schemas: o painel não deve buscar
 * isto a cada mensagem.
 *
 * Devolve `null` quando o servidor não responde, e o prompt diz ao modelo que
 * não há vocabulário. Esse é o ponto: o caminho degradado é dizer que não
 * sabe, e não chutar os nomes.
 */
let _vocabAmplia = null;
let _vocabEm = 0;
const TTL_VOCAB = 10 * 60 * 1000;

export async function vocabularioAmplia() {
  const agora = Date.now();
  if (_vocabAmplia && agora - _vocabEm < TTL_VOCAB) return _vocabAmplia;
  try {
    const r = await apiFetch('/api/amplia/vocabulario/');
    // `cabe: false` significa que o servidor teve de cortar a lista para caber.
    // Passamos o texto na mesma, com a marca de corte — é melhor o modelo
    // saber que a lista está incompleta do que achar que é tudo.
    _vocabAmplia = (r && r.texto) || null;
    _vocabEm = agora;
    if (_vocabAmplia && r && r.cabe === false) {
      console.warn('[IA] vocabulario incompleto pelo servidor:', r.chars, 'chars');
    }
  } catch (e) {
    console.warn('[IA] vocabulario indisponivel:', e && e.message);
    _vocabAmplia = null;
  }
  return _vocabAmplia;
}

/** O trecho que entra no system prompt: o vocabulário, ou a ausência dele. */
async function blocoFerramentas() {
  const v = await vocabularioAmplia();
  if (!v) {
    return (
      'FERRAMENTAS: esta instância não conseguiu obter a lista do servidor, ' +
      'por isso não tem ferramentas disponíveis agora. Responda com texto ' +
      'normal e diga que precisa de recarregar a página para voltar a agir.'
    );
  }
  return v;
}

function getCsrf() {
  return (
    document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
    document.cookie
      .split('; ')
      .find((c) => c.startsWith('csrftoken='))
      ?.split('=')[1] ||
    ''
  );
}
async function apiFetch(url, opts = {}) {
  const headers = { 'X-CSRFToken': getCsrf(), ...(opts.headers || {}) };
  if (opts.body && !(opts.body instanceof FormData) && !headers['Content-Type'])
    headers['Content-Type'] = 'application/json';
  const r = await fetch(url, { credentials: 'same-origin', cache: 'no-store', ...opts, headers });
  const text = await r.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    data = text;
  }
  if (!r.ok) {
    const msg =
      data?.detail ||
      data?.erro ||
      data?.error ||
      JSON.stringify(data).slice(0, 400) ||
      `HTTP ${r.status}`;

    // 401/403 NAO sao "a API nao respondeu" — sao "a sessao morreu". Sao
    // deliberately distinguidos de um 500 porque o chamador trata os dois
    // igual: `entenderSistema()` e os intents fazem `.catch(() => null)` em
    // TUDO, e um 403 engolido em `null` e' indistinguivel de "a fazenda nao
    // tem dados". E' o caminho que produz um painel de zeros sem ninguem
    // perceber que o motivo e' falta de sessao.
    //
    // MEDIDO, 2026-10-04: sem isto, um visitante anonimo em `/` recebia
    // respostas 403 de todas as 7 chamadas de `entenderSistema`, todas
    // viravam `null`, e cada KPI caia no seu `|| 0` — o painel inteiro
    // "funcionava" com numeros que nao eram de ninguem.
    if (r.status === 401 || r.status === 403) {
      if (typeof window !== 'undefined' && !window.__ampliaSemSessao) {
        window.__ampliaSemSessao = true;
        const prox = typeof location !== 'undefined' ? location.pathname + location.search : '/';
        location.href = '/login/?next=' + encodeURIComponent(prox);
      }
      // `semSessao` e' lido pelos chamadores que fazem `.catch(() => null)`:
      // distingue "o servidor disse que nao" de "o servidor nao respondeu".
      const e = new Error(msg);
      e.semSessao = true;
      e.status = r.status;
      throw e;
    }
    // O `status` viaja com o erro em QUALQUER falha, não só em 401/403.
    //
    // Só o 401/403 o punha, e o resultado é que um 503 — que é onde o
    // servidor ESCREVE o motivo ("cadastre a cidade/UF") — chegava ao
    // chamador como um `Error` sem nada além da mensagem. Um chamador que
    // distinga "o servidor não respondeu" de "o servidor respondeu que não
    // pode" não conseguia: os dois eram a mesma coisa. O texto estava lá;
    // faltava o facto que o acompanha.
    const erro = new Error(msg);
    erro.status = r.status;
    throw erro;
  }
  return data;
}
let _ctxCache = null,
  _ctxTime = 0;
async function entenderSistema() {
  if (_ctxCache && Date.now() - _ctxTime < 60000) return _ctxCache;
  try {
    const [props, talhoes, safras, culturas, estoque, fin, dash] = await Promise.all([
      apiFetch('/api/propriedades/').catch(() => null),
      apiFetch('/api/talhoes/?page_size=5').catch(() => null),
      apiFetch('/api/safras/?page_size=5').catch(() => null),
      apiFetch('/api/culturas/').catch(() => null),
      apiFetch('/api/estoque/?page_size=5').catch(() => null),
      apiFetch('/api/financeiro/').catch(() => null),
      apiFetch('/api/dashboard/').catch(() => null),
    ]);
    const ctx = [];
    try {
      window._iaPropPadrao = props?.results?.[0]?.id || window._iaPropPadrao || null;
    } catch {}
    if (props?.results?.length)
      ctx.push(
        `Propriedades: ${props.results.map((p) => p.nome).join(', ')} (${props.count} total)`
      );
    if (talhoes?.results?.length)
      ctx.push(
        `Talhões: ${talhoes.results
          .map((t) => `${t.nome}${t.area ? ' (' + t.area + 'ha)' : ''}`)
          .join(', ')} (${talhoes.count} total)`
      );
    if (safras?.results?.length)
      ctx.push(
        `Safras: ${safras.results
          .map(
            (s) =>
              `${s.nome || s.ano}${s.producao_total ? ' - prod:' + s.producao_total + 't' : ''}`
          )
          .join(', ')}`
      );
    if (culturas?.results?.length)
      ctx.push(`Culturas: ${culturas.results.map((c) => c.nome).join(', ')}`);
    if (estoque?.results?.length)
      ctx.push(`Estoque: ${estoque.count || estoque.results.length} itens`);
    if (fin) {
      const fp = [];
      if (fin.fluxo_caixa != null) fp.push(`fluxo: ${fmtMoeda(fin.fluxo_caixa)}`);
      if (fin.saldo != null) fp.push(`saldo: ${fmtMoeda(fin.saldo)}`);
      if (fin.total_receitas != null) fp.push(`receitas: ${fmtMoeda(fin.total_receitas)}`);
      ctx.push(`Financeiro: ${fp.length ? fp.join(', ') : 'disponível'}`);
    }
    if (dash) {
      const dp = [];
      if (dash.producao_total != null) dp.push(`produção total: ${fmtNum(dash.producao_total)}t`);
      if (dash.area_total != null) dp.push(`área: ${fmtNum(dash.area_total)}ha`);
      if (dp.length) ctx.push(`Dashboard: ${dp.join(', ')}`);
    }
    _ctxCache = ctx.join(' | ') || 'Sistema Ampliagro carregado';
    _ctxTime = Date.now();
    return _ctxCache;
  } catch {
    return 'Sistema Ampliagro';
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// CONSENTIMENTO ANTES DE DESCARREGAR O MODELO. MEDIDO 2026-10-04 (agente 4).
//
// O que acontecia: `iaInit()` era chamado e o `engine.reload(iaModel)` ia
// buscar o SmolLM2-1.7B — **1,1 GB** — pela rede móvel do produtor, sem
// perguntar nada. O relatório de arquitectura aponta isto como P0 e tem razão
// com um agravante: o produto é usado no talhão, onde a rede é escassa e os
// dados são pagos por megabyte.
//
// Decidir isto no código, e não numa nota de rodapé:
//
//   1. **O tamanho é conhecido.** `IA_MODELOS` abaixo. Um download de 1,1 GB
//      que ninguém decidiu é uma decisão tomada em nome do produtor.
//   2. **A capacidade do aparelho também é conhecida, quando o browser
//      a diz.** `navigator.deviceMemory` é o que existe destandards-compliant
//      para isto. Debaixo do minimo declarado, avisamos — e o aviso diz
//      quantos GB faltam, não só que "pode falhar".
//   3. **Consentimento é persistido.** `localStorage` guarda a decisão, para
//      que a pergunta não repita a cada `iaInit()`. E recuso explícito
//      (`'nao'`) também persiste — senão cada navegação volta a perguntar, e
//      uma pergunta que se repete até o utilizador desistir não é
//      consentimento: é assédio.
//   4. **Recusar não é quebrar.** O motor de servidor (`iaReady = 'server'`)
//      é o caminho e funciona. A IA na borda é um extra, não a base. Um
//      produtor sem dados deve ter o sistema inteiro.
//
// RAM aproximada não mede VRAM nem o tamanho máximo de um buffer WebGPU.
// O adapter e os requisitos do catálogo são verificados antes de reload().
// Limites desconhecidos ainda podem falhar no runtime: mantém-se o servidor.
// ─────────────────────────────────────────────────────────────────────────────

const IA_MODELOS = {
  'SmolLM2-1.7B-Instruct-q4f16_1-MLC': {
    rotulo: 'SmolLM2 1.7B',
    bytes: 1.1e9,
    memoriaRecomendada: 2.0e9,
    required_features: ['shader-f16'],
  },
  'Qwen2-0.5B-Instruct-q4f16_1-MLC': {
    rotulo: 'Qwen2 0.5B',
    bytes: 3.5e8,
    memoriaRecomendada: 1.0e9,
    required_features: ['shader-f16'],
  },
};

const IA_CONSENTIMENTO_KEY = 'ampliagro_ia_consent_' + (window.AMPLIAGRO_UID || 'default');

function _iaMemoriaDispositivo() {
  // `deviceMemory` é a unica medicao de capacidade que o browser expoe de
  // forma standard. Chromium devolve GiB arredondado a {0.25, 0.5, 1, 2, 4, 8}.
  // Firefox e Safari nao implementam — e `null` significa "nao sabemos", o que
  // e diferente de "nao ha memoria". A distincao importa: "nao sabemos"
  // pergunta; "nao ha" recusa.
  if (typeof navigator === 'undefined') return null;
  return typeof navigator.deviceMemory === 'number' ? navigator.deviceMemory * 1024 ** 3 : null;
}

function _iaConsentimento(modelo) {
  const reg = IA_MODELOS[modelo];
  if (!reg) return true; // modelo desconhecido: nao inventamos um limiar

  // Costura para os testes. `tests/e2e/pwa-offline.spec.ts` procurava
  // `window.iaMotorConsentido` e verificava `existe || true` — que é uma
  // tautologia: `existe || true` é sempre verdadeiro, e a asserção nunca
  // podia falhar. O teste parecia guardar o consentimento e não guardava.
  //
  // Agora a costura existe E é honesta: `iaMotorConsentido(false)` nega o
  // consentimento sem perguntar, e `iaMotorConsentido(true)` concede-o. Um
  // teste pode assim verificar os dois ramos sem depender de um `confirm()`.
  //
  // Risco assumido: isto é um seam client-side, portanto qualquer script da
  // página o pode chamar. O que ele desbloqueia é o download, pela conta e
  // pelo armazenamento do utilizador — que é dele. Não é uma autorização de
  // servidor, e não deve ser lido como uma.
  if (typeof window.iaForcarConsentimentoIA === 'boolean') {
    return window.iaForcarConsentimentoIA;
  }

  try {
    const guardado = localStorage.getItem(IA_CONSENTIMENTO_KEY + '_' + modelo);
    if (guardado === 'sim') return true;
    if (guardado === 'nao') return false;
  } catch (e) {
    /* sem localStorage: perguntamos a cada vez, que e' o comportamento seguro */
  }

  const gb = (reg.bytes / 1e9).toFixed(1).replace('.', ',');
  const memoria = _iaMemoriaDispositivo();
  let aviso = '';
  if (memoria !== null && memoria < reg.memoriaRecomendada) {
    aviso =
      '\n\nATENÇÃO: este aparelho declara ' +
      (memoria / 1e9).toFixed(0) +
      ' GB de memória e este modelo precisa de ~' +
      (reg.memoriaRecomendada / 1e9).toFixed(0) +
      ' GB. Pode fechar o navegador por falta de memória.';
  }

  const resposta = window.confirm(
    'O Ampliagro pode usar inteligência artificial NO SEU APARELHO, sem enviar ' +
      'nada para um servidor externo.\n\n' +
      'Para isso vai descarregar o modelo "' +
      reg.rotulo +
      '" (' +
      gb +
      ' GB) uma vez, e guardá-lo no aparelho. ' +
      'Depois disso funciona sem rede.\n\n' +
      'Se preferir, o Ampliagro continua a funcionar sem esta feature — a IA ' +
      'passa a responder pelo servidor.' +
      aviso +
      '\n\nDescarregar ~' +
      gb +
      ' GB agora?'
  );

  try {
    localStorage.setItem(IA_CONSENTIMENTO_KEY + '_' + modelo, resposta ? 'sim' : 'nao');
  } catch (e) {
    /* sem persistencia: perguntamos de novo */
  }
  return resposta;
}

/**
 * A COSTURA PÚBLICA. É esta que `tests/e2e/pwa-offline.spec.ts` procura.
 *
 *   window.iaMotorConsentido(true)   → concede, sem perguntar
 *   window.iaMotorConsentido(false)  → nega, sem perguntar
 *   window.iaMotorConsentido()       → o que esta gravado, ou null
 *
 * Devolve o valor gravado, para o teste poder afirmar em vez de supor.
 */
window.iaMotorConsentido = function (resposta) {
  if (typeof resposta === 'boolean') {
    window.iaForcarConsentimentoIA = resposta;
    try {
      localStorage.setItem(IA_CONSENTIMENTO_KEY + '_' + iaModel, resposta ? 'sim' : 'nao');
    } catch (e) {
      /* sem persistencia: a forca ainda vale nesta sessao */
    }
    return resposta;
  }
  try {
    const guardado = localStorage.getItem(IA_CONSENTIMENTO_KEY + '_' + iaModel);
    return guardado === 'sim' ? true : guardado === 'nao' ? false : null;
  } catch (e) {
    return null;
  }
};

export function obterDiagnosticoIaLocal() {
  return { ...iaDiagnostico };
}

/** API presente não garante adapter: drivers, políticas e Android podem recusá-lo. */
export async function verificarWebGPU() {
  if (globalThis.isSecureContext === false) return { motivo: 'contexto-inseguro' };
  if (typeof navigator === 'undefined' || !navigator.gpu?.requestAdapter) {
    return { motivo: 'webgpu-indisponivel' };
  }
  try {
    const adapter = await navigator.gpu.requestAdapter();
    return adapter ? { adapter } : { motivo: 'adaptador-indisponivel' };
  } catch (e) {
    return { motivo: 'adaptador-indisponivel' };
  }
}

/** Usa limites por buffer, nunca RAM do aparelho como suposta VRAM. */
export function incompatibilidadeModelo(adapter, registro) {
  if (!registro) return 'modelo-fora-do-catalogo';
  if ((registro.required_features || []).some((f) => !adapter.features?.has(f))) {
    return 'recurso-gpu-ausente';
  }
  const bytes = registro.buffer_size_required_bytes;
  if (
    bytes &&
    (!adapter.limits ||
      bytes > adapter.limits.maxStorageBufferBindingSize ||
      bytes > adapter.limits.maxBufferSize)
  )
    return 'limite-buffer';
  return '';
}

function _iaServidor(motivo, onProgress) {
  iaEngine = null;
  iaReady = 'server';
  iaDiagnostico = { modo: 'servidor', motivo, modelo: null };
  if (onProgress)
    onProgress({ text: 'IA local indisponível; atendimento pelo servidor quando houver conexão.' });
  return null;
}

async function _iaInicializar(onProgress, carregarRuntime) {
  const { adapter, motivo } = await verificarWebGPU();
  if (!adapter) return _iaServidor(motivo, onProgress);
  let webllm;
  let ultimoMotivo = 'modelo-incompativel';
  const candidatos = [...new Set([iaModel, 'Qwen2-0.5B-Instruct-q4f16_1-MLC'])];
  for (const modelo of candidatos) {
    // Requisitos conhecidos da versão fixada; não precisa baixar o runtime
    // nem perguntar pelo modelo quando falta shader-f16.
    let incompatibilidade = incompatibilidadeModelo(adapter, IA_MODELOS[modelo]);
    if (incompatibilidade) {
      ultimoMotivo = incompatibilidade;
      continue;
    }
    if (webllm) {
      incompatibilidade = incompatibilidadeModelo(
        adapter,
        webllm.prebuiltAppConfig?.model_list?.find((r) => r.model_id === modelo)
      );
      if (incompatibilidade) {
        ultimoMotivo = incompatibilidade;
        continue;
      }
    }
    if (!_iaConsentimento(modelo)) {
      console.info('[IA] produtor recusou o download do modelo; modo servidor.');
      return _iaServidor('download-recusado', onProgress);
    }
    if (!webllm) {
      try {
        webllm = await carregarRuntime();
      } catch (e) {
        return _iaServidor('runtime-indisponivel', onProgress);
      }
    }
    incompatibilidade = incompatibilidadeModelo(
      adapter,
      webllm.prebuiltAppConfig?.model_list?.find((r) => r.model_id === modelo)
    );
    if (incompatibilidade) {
      ultimoMotivo = incompatibilidade;
      continue;
    }
    let engine;
    try {
      engine = new webllm.MLCEngine();
      engine.setInitProgressCallback((p) => {
        if (onProgress) onProgress(p);
      });
      iaDiagnostico = { modo: 'carregando', motivo: '', modelo };
      await engine.reload(modelo);
      iaEngine = engine;
      iaModel = modelo;
      iaReady = true;
      iaDiagnostico = { modo: 'local', motivo: '', modelo };
      return engine;
    } catch (e) {
      console.warn('[IA] falha ao carregar modelo local', modelo, e);
      ultimoMotivo = 'carregamento-falhou';
      // Libera buffers do modelo falho ANTES de tentar outro na mesma GPU.
      try {
        if (engine) await engine.unload();
      } catch (erro) {
        return _iaServidor('liberacao-gpu-falhou', onProgress);
      }
    }
  }
  return _iaServidor(ultimoMotivo, onProgress);
}

function iaInit(
  onProgress,
  carregarRuntime = () => import('https://esm.run/@mlc-ai/web-llm@0.2.79')
) {
  if (iaEngine) return Promise.resolve(iaEngine);
  if (!iaInicializacao) {
    // Chat e áudio podem iniciar juntos; ambos compartilham um único download.
    iaInicializacao = _iaInicializar(onProgress, carregarRuntime).finally(() => {
      iaInicializacao = null;
    });
  }
  return iaInicializacao;
}

function analisarIntent(texto, contextoAtual) {
  // ═══════════════════════════════════════════════════════════════
  // AMPLIA ABSOLUTA — Análise inteligente: nunca desviar, perguntar se faltar
  // ═══════════════════════════════════════════════════════════════
  const t = (texto || '').toLowerCase();
  const ctx = contextoAtual || {};
  const intencao = { tipo: 'desconhecida', falta: [], pergunta: null, acao: null };

  // 1. Clima / meteorologia (inclui "chover" — a pergunta nº 1)
  //
  // NÃO se decide aqui de onde vem o tempo. Decidia-se, e as DUAS condições
  // eram sempre falsas:
  //
  //   `ctx.estacoes` — `PropriedadeSerializer` não tem um campo `estacoes`
  //     (a relação chama-se `estacoes_meteo`), logo `prop.estacoes` era
  //     sempre `undefined` e a lista, sempre vazia. A pergunta "a sua fazenda
  //     não tem estação cadastrada" era feita mesmo com estações no banco.
  //
  //   `window.OPENWEATHER_API_KEY` — a chave vive em `settings.py`, no
  //     servidor. No browser a variável nunca existiu, e não existe hoje.
  //
  // Duas condições sempre falsas tornam `!temEstacao && !temChaveOWM` uma
  // TAUTOLOGIA: o agente perguntava de onde queria o tempo em TODA pergunta
  // de clima e nunca consultava a previsão — que era o que o produtor
  // tinha pedido.
  //
  // Quem responde agora é a fonte real, um passo abaixo na cascata
  // (`smartResponse`). E quando a fonte calar, quem explica porquê é o erro
  // que o servidor devolveu, não esta função a adivinhar.
  if (t.match(/(clima|tempo|previsão|previsao|chuva|chover|temp|umidade|vento)/)) {
    intencao.tipo = 'consultar';
    intencao.acao = 'clima';
    intencao.falta = [];
    intencao.pergunta = null;
    return intencao;
  }

  // 2. Detectar cadastro
  if (
    t.match(
      /(cadastrar|criar|adicionar|nova|inserir).*?(funcion|safra|talh|estoque|opera|insumo|maquina|animal|cultura|propriedade)/
    )
  ) {
    intencao.tipo = 'criar';
    // Identifica recurso pelo texto
    const map = {
      funcionario: 'funcionarios',
      safra: 'safras',
      talhao: 'talhoes',
      estoque: 'estoque',
      operacao: 'operacoes',
      insumo: 'insumos',
      maquinario: 'maquinarios',
      animal: 'animais',
      cultura: 'culturas',
      propriedade: 'propriedades',
    };
    for (const [k, v] of Object.entries(map)) if (t.includes(k)) intencao.acao = v;
    // Pergunta adaptativa baseada em esquema
    const esquema = ESQUEMAS_CADASTRO[intencao.acao];
    if (esquema && esquema.length > 0) {
      intencao.falta = esquema.map((e) => e.campo);
      intencao.pergunta = `Para cadastrar ${intencao.acao}: ${esquema[0].pergunta}`;
    }
    return intencao;
  }

  // 3. Detectar edição / alteração
  if (
    t.match(
      /(editar|alterar|mudar|atualizar).*?(funcion|safra|talh|estoque|opera|insumo|maquina|animal)/
    )
  ) {
    intencao.tipo = 'editar';
    const map = {
      funcionario: 'funcionarios',
      safra: 'safras',
      talhao: 'talhoes',
      estoque: 'estoque',
      operacao: 'operacoes',
      insumo: 'insumos',
      maquinario: 'maquinarios',
      animal: 'animais',
    };
    for (const [k, v] of Object.entries(map)) if (t.includes(k)) intencao.acao = v;
    intencao.falta = ['id_registro'];
    intencao.pergunta = `Qual registro você quer editar (${intencao.acao})? Me o nome, ID ou diga "último".`;
    return intencao;
  }

  // 4. Detectar consulta / leitura
  if (
    t.match(
      /(mostrar|ver|listar|consultar|puxar|falar|exibir|buscar).*?(estoque|financeiro|caixa|safra|talh|propriedade|fazenda|cultura|insumo|maquina|funcion|animal|sensor|opera)/
    )
  ) {
    intencao.tipo = 'consultar';
    intencao.acao = 'dados_gerais';
    return intencao;
  }

  // 5. Navegação
  if (
    t.match(
      /(abrir|ir para|navegar).*?(safra|talh|estoque|financeiro|agenda|caminh|sensor|funcion|cultura|propriedade)/
    )
  ) {
    intencao.tipo = 'navegar';
    return intencao;
  }

  if (
    t.match(/(clima|tempo|previsão|previsao).*?(alterosa|primavera|mt|mg|cidade)/) ||
    (t.includes('clima') && t.includes('alterosa'))
  ) {
    // ══ CORREÇÃO TESTE REAL: clima não inicia wizard direto ══
    // Só pergunta opções; só inicia wizard se usuário confirmar (a) explicitamente
    intencao.tipo = 'consultar';
    intencao.acao = 'clima';
    intencao.falta = ['fonte_clima'];
    intencao.pergunta = `Você está em ${ctx.cidade || 'Alterosa'}/${
      ctx.uf || 'MT'
    }. Confirmo: quer (a) cadastrar estação meteorológica no campo, (b) usar previsão pela internet (INMET/OpenWeather), ou (c) ver sensores?`;
    return intencao;
  }
  // ══ Resposta curta a (a)/(b)/(c) da pergunta de fonte de clima ══
  // Ex: usuário responde só "B", "letra b", "opção b" — o caso mais natural.
  // (só casa a mensagem INTEIRA, para não sequestrar texto normal)
  const mOpcao = t.match(/^\s*(?:op[cç][aã]o\s+|letra\s+)?([abc])\s*[).:]?\s*$/);
  if (mOpcao) {
    const op = mOpcao[1];
    if (op === 'b') {
      intencao.tipo = 'consultar';
      intencao.acao = 'clima';
      intencao.falta = [];
      intencao.pergunta = null; // já escolheu — previsão pela internet
      return intencao;
    }
    if (op === 'a') {
      intencao.tipo = 'criar';
      intencao.acao = 'estacoes';
      intencao.falta = ['nome', 'latitude', 'longitude'];
      intencao.pergunta =
        'Confirmo: cadastrar nova estação meteorológica. Nome da estação? (Ex: Estação Fazenda Norte)';
      return intencao;
    }
    // op === 'c' → ver sensores existentes
    intencao.tipo = 'consultar';
    intencao.acao = 'sensores';
    intencao.falta = [];
    intencao.pergunta = null;
    return intencao;
  }
  // Se já respondeu opção b / internet / previsão pela internet → interpretar como consulta web
  if (
    t.match(/(opção b|opção\s+b|previsão pela internet|internet|b\)|b\s+\)|usar.*web)/) ||
    (t.includes('b') && (t.includes('internet') || t.includes('previsão')))
  ) {
    intencao.tipo = 'consultar';
    intencao.acao = 'clima';
    intencao.falta = [];
    intencao.pergunta = null; // já escolheu — prossegue para consulta web
    return intencao;
  }
  // Se confirma cadastro de estação meteorológica → iniciar wizard estacoes (ignorar outro wizard se for o caso)
  if (
    (t.match(/(estação meteorológica|estacao)/) || t.includes('estação')) &&
    (t.match(/(cadastrar|criar|novo|vou cadastrar)/) || t.includes('cadastrar'))
  ) {
    intencao.tipo = 'criar';
    intencao.acao = 'estacoes';
    intencao.falta = ['nome', 'latitude', 'longitude'];
    intencao.pergunta =
      'Confirmo: cadastrar nova estação meteorológica. Nome da estação? (Ex: Estação Fazenda Norte)';
    return intencao;
  }
  if (
    t.match(
      /(maior|mais|quantia|quantidade|maior quantia).*?(cadastro|culturas?|safra|talh|producao|estoque|animais?|funcionarios?) /
    )
  ) {
    intencao.tipo = 'consultar';
    intencao.acao = 'agregacao';
    intencao.falta = ['campo_agregacao'];
    intencao.pergunta = `Confirmo: você quer saber qual ${
      t.includes('cultura') ? 'cultura' : 'recurso'
    } tem a maior quantidade cadastrada? Vou consultar o banco (Cultura / Safra / Talhão / Animal).`;
    return intencao;
  }

  // 8. Cidade / localização / onde estou — consultar Propriedade real
  if (
    t.match(
      /(em qual cidade|onde estou|localiza|cidade|estado|uf).*?(estou|estamos|fica|ficamos)/
    ) ||
    t.includes('cidade que eu estou')
  ) {
    intencao.tipo = 'consultar';
    intencao.acao = 'propriedade';
    intencao.falta = ['propriedade_cidade'];
    intencao.pergunta =
      'Vou consultar sua propriedade cadastrada. Posso confirmar: você está em qual cidade/estado? (Ex: Alterosa/MG)';
    return intencao;
  }

  // 9. Modo claro / tema / escuro — editar PerfilUsuario (não inventar)
  if (
    t.match(/(modo claro|claro|escuro|tema).*?(mudar|mude|alterar|ativar)/) ||
    t.includes('mude para o modo claro')
  ) {
    intencao.tipo = 'editar';
    intencao.acao = 'perfil';
    intencao.falta = ['tema'];
    intencao.pergunta =
      'Confirmo: você quer alterar o tema do perfil? (claro / escuro). Vou atualizar seu PerfilUsuario.';
    return intencao;
  }

  // 10. Repetir texto / letra — NÃO inventar texto repetido; perguntar contexto
  if (t.match(/(repita|repetir).*?(a|letra|texto|palavra)/) || t.includes('repita a letra')) {
    intencao.tipo = 'perguntar';
    intencao.falta = ['texto_repetir'];
    intencao.pergunta =
      'Quero confirmar: qual letra ou texto você quer repetir? E quantas vezes? (Não vou inventar — vou repetir exatamente o que confirmar.)';
    return intencao;
  }

  // 11. Abrir YouTube / site externo — navegar se permitido; se não reconhecido → pergunta
  if (t.match(/(abrir|ir para).*?(youtube|google|site|web)/)) {
    intencao.tipo = 'navegar';
    intencao.acao = 'navegar_externo';
    intencao.falta = ['destino_url'];
    intencao.pergunta =
      'Confirmo: você quer abrir uma página externa? Posso abrir YouTube (youtube.com) se confirmar. Não vou inventar conteúdo da página.';
    return intencao;
  }

  // 6. Pergunta livre / não reconhecida → não desviar, perguntar contexto
  // (só entra se não foi detectado por nenhum dos anteriores)
  if (t.length > 2 && intencao.tipo === 'desconhecida') {
    intencao.tipo = 'perguntar';
    intencao.falta = ['contexto'];
    intencao.pergunta = `Entendi sua mensagem: "${texto}". Como posso ajudar? Você quer consultar, cadastrar, editar, navegar ou receber uma recomendação? Diga o recurso (ex: safra, estoque, clima, funcionário). Exemplos que respondo na hora: "vai chover?", "resumo da safra", "estoque baixo", "ligue o irrigador", "quais tarefas?".`;
  }
  return intencao;
}

function perguntarSequencial(pergunta, contexto) {
  // Gera resposta de pergunta em linguagem natural (nunca JSON bruto)
  return pergunta || 'Preciso de mais informações para ajudar. Pode confirmar?';
}

function fallbackIntent(text) {
  const tRaw = text.toLowerCase();
  const t = tRaw.normalize('NFD').replace(/[\u0300-\u036f]/g, '');

  // ══ CORREÇÃO ERROS REAL — NÃO RETORNAR TEXTO FIXO DE REGRAS ══
  // Se não reconhece: NÃO inventar. Passa para analisarIntent() (já implementado) ou retorna null.
  // Antes: retornava REGRAS['soilType'] etc. — causa de todas as respostas sem sentido.
  // Agora: apenas reconhece navegação/consulta/criar explícitos. O resto é tratado pelo protocolo.

  // navegar — apenas para verbos de navegação explícitos + destino conhecido
  for (const [k, path] of Object.entries(PAGINAS)) {
    const pathWords = path.replace(/[\/_]/g, ' ').trim();
    const pathMatch = pathWords.length > 3 && t.includes(pathWords);
    if (t.includes(k) || pathMatch) {
      if (t.includes('abrir') || t.includes('ir para') || t.includes('navegar')) {
        return `{"tool":"navegar","args":{"destino":"${k}"}}`;
      }
    }
  }
  if (
    t.match(
      /(abrir|ir para|navegar).*(safra|talh|estoque|financeiro|agenda|caminh|sensor|funcion|cultura|propriedade|fazenda|insumo|maquina)/
    )
  ) {
    const map = {
      safra: 'safras',
      talh: 'talhoes',
      estoque: 'estoque',
      financeiro: 'lancamentos',
      agenda: 'operacoes',
      caminh: 'maquinarios',
      sensor: 'sensores',
      funcion: 'funcionarios',
      cultura: 'culturas',
      propriedade: 'propriedades',
      fazenda: 'propriedades',
      insumo: 'insumos',
      maquina: 'maquinarios',
    };
    for (const [kw, dest] of Object.entries(map))
      if (t.includes(kw)) return `{"tool":"navegar","args":{"destino":"${dest}"}}`;
  }
  // consultar - falar/puxar/mostrar/listar dados
  if (
    t.match(
      /(mostrar|ver|listar|consultar|puxar|falar|exibir|buscar).*(estoque|financeiro|caixa|safra|talh|propriedade|fazenda|cultura|insumo|maquina|funcion|animal|sensor|opera)/
    )
  ) {
    const map2 = {
      estoque: 'estoque',
      financeiro: 'lancamentos',
      caixa: 'lancamentos',
      safra: 'safras',
      talh: 'talhoes',
      propriedade: 'propriedades',
      fazenda: 'propriedades',
      cultura: 'culturas',
      insumo: 'insumos',
      maquina: 'maquinarios',
      funcion: 'funcionarios',
      animal: 'animais',
      sensor: 'sensores',
      opera: 'operacoes',
    };
    for (const [kw, rec] of Object.entries(map2))
      if (t.includes(kw)) return `{"tool":"consultar","args":{"recurso":"${rec}"}}`;
  }
  if (t.includes('estoque') && (t.includes('ver') || t.includes('mostrar') || t.includes('falar')))
    return `{"tool":"consultar","args":{"recurso":"estoque"}}`;
  if (t.includes('financeiro') || t.includes('caixa'))
    return `{"tool":"consultar","args":{"recurso":"lancamentos"}}`;
  // iniciar wizard para cadastros incompletos
  if (
    t.match(
      /(cadastrar|cadastra|criar|inserir|adicionar|nova|associar|vincular).*(funcion|safra|talh|estoque|opera|insumo|maquina|animal|cultura|propriedade)/
    )
  ) {
    const map3 = {
      opera: 'operacoes',
      funcion: 'funcionarios',
      safra: 'safras',
      talh: 'talhoes',
      estoque: 'estoque',
      insumo: 'insumos',
      maquina: 'maquinarios',
      animal: 'animais',
      cultura: 'culturas',
      propriedade: 'propriedades',
    };
    for (const [kw, rec] of Object.entries(map3))
      if (t.includes(kw)) return `{"tool":"iniciar_cadastro","args":{"recurso":"${rec}"}}`;
  }
  /* == AQUI NAO SE CRIA NADA. ==
   *
   * Este bloco emitia, para qualquer frase que combinasse "criar" com um nome de
   * recurso, um tool call de ESCRITA com dados fabricados:
   *
   *     {"tool":"criar","args":{"recurso":"safras","dados":{"nome":"Novo safras",...}}}
   *
   * A tool `amplia_criar` NAO existe no catalogo, portanto hoje isto nao grava:
   * `toolCallGovernada` normaliza o prefixo e o servidor devolve
   * `tool_fora_do_catalogo`. Era por isso que o produtor via uma lista de nomes
   * de ferramentas internas em vez de uma resposta.
   *
   * Mas era uma ARMADILHA ARMADA: no dia em que alguem adicionasse `amplia_criar`
   * ao catalogo, estas duas linhas passavam a gravar lixo na base do produtor sem
   * ele pedir — um registo chamado "Novo safras", sem os campos obrigatorios, que
   * o produtor nunca veria aparecer e que lheSUJARIA os relatorios.
   *
   * Criar registo passa pelo caminho do servidor (`amplia_cadastrar_*`), que
   * exige `needs_confirm`. O cliente NUNCA inventa `dados` — Principio 7 da
   * camada amplia, que este bloco violava em silencio.
   *
   * Para NAVEGAR e CONSULTAR, os nomes verdadeiros estao em `PAGINAS` e
   * `RECURSOS_API`; as tools `navegar`/`consultar` legadas tambem nao existem
   * (ver o comentario das 5431-5436). Deixar cair ao `null` abaixo e o
   * comportamento correto: o `iaChat` mostra o texto honesto da linha 5428,
   * "Nao consegui processar agora...".
   */

  // clima / tempo
  if (t.match(/(chover|chuva|previsao|previsão|tempo|clima)/)) {
    return `{"tool":"consultar","args":{"recurso":"clima"}}`;
  }
  // tarefas do dia
  if (
    t.match(/(tarefas|agenda|operações|operaçoes).*(hoje|dia|agora)/) ||
    t.match(/quais.*tarefas/)
  ) {
    return `{"tool":"consultar","args":{"recurso":"operacoes","filtros":{"hoje":1}}}`;
  }
  // preço da saca / commodities
  if (
    t.match(
      /(preço|preco|saca|cotação|cotacao|commodity|valor).*(soja|milho|cafe|café|algod|trigo|arroz|boi|gado|sorgo)/
    )
  ) {
    const produtos = [
      'soja',
      'milho',
      'cafe',
      'café',
      'algodao',
      'algodão',
      'trigo',
      'arroz',
      'boi',
      'sorgo',
    ];
    for (const p of produtos)
      if (t.includes(p))
        return `{"tool":"consultar","args":{"recurso":"commodities","filtros":{"produto":"${p}"}}}`;
    return `{"tool":"consultar","args":{"recurso":"commodities"}}`;
  }
  if (t.match(/(preço|preco|saca|cotação).*(soja|milho)/)) {
    return `{"tool":"consultar","args":{"recurso":"commodities"}}`;
  }
  // irrigação ligar/desligar
  if (t.match(/(ligar|ligue|acionar|desligar|desligue).*(irrig|aspersor|piv[oô]|bomba)/)) {
    const acao = t.includes('deslig') ? 'desligar' : 'ligar';
    const talhaoMatch = t.match(/talh[aã]o\s*([a-z0-9\- ]+)/);
    const talhao = talhaoMatch ? talhaoMatch[1].trim() : '';
    return `{"tool":"irrigacao","args":{"acao":"${acao}","talhao":"${talhao}"}}`;
  }
  // vacinas animal
  if (
    t.match(/(vacina|vacinas|vacinado).*(animal|brinco|boi|gado)/) ||
    t.match(/animal.*vacina/) ||
    t.includes('vacinado')
  ) {
    const brincoMatch = t.match(/(brinco|animal)\s*([a-z0-9\-]+)/);
    const brinco = brincoMatch ? brincoMatch[2] : '';
    if (brinco)
      return `{"tool":"consultar","args":{"recurso":"eventos-sanitarios","filtros":{"animal":"${brinco}"}}}`;
    return `{"tool":"consultar","args":{"recurso":"eventos-sanitarios"}}`;
  }
  if (t.includes('producao') || t.includes('produção')) {
    return `{"tool":"consultar","args":{"recurso":"safras"}}`;
  }
  if (t.includes('fluxo') && t.includes('caixa')) {
    return `{"tool":"consultar","args":{"recurso":"lancamentos"}}`;
  }
  if (t.includes('relatorio') || t.includes('relatório')) {
    return `{"tool":"consultar","args":{"recurso":"relatorios-gerados"}}`;
  }
  if (t.match(/quais.*(cadastro|salao|salão|cafe|café)/)) {
    return `{"tool":"consultar","args":{"recurso":"culturas"}}`;
  }
  return null;
}

/* ══ PONTE SANDBOX — liga o chat aos 19 intents do servidor (/api/ia/) ══
   Sem ela, o chat só usa regex local e cai no "Entendi sua mensagem..." para
   quase tudo (ex: "vai chover" não casava "chuva"). Roda ANTES do fluxo antigo:
   se resolve com confiança, responde direto; senão devolve null e o fluxo segue. */
let _sbCatalog = null;

function _sbNorm(s) {
  return (s || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');
}

function _sbExtrairParams(texto, intent) {
  const params = {};
  const mCid = texto.match(/(?:para|em)\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)?)/);
  if (
    mCid &&
    ['clima_agora', 'vai_chover', 'previsao_estendida', 'melhor_pulverizar'].includes(intent)
  ) {
    params.cidade = mCid[1];
  }
  const mH = texto.match(/(\d+)\s*h/);
  if (mH && intent === 'vai_chover') params.horas = Math.min(Math.max(parseInt(mH[1]), 1), 72);
  if (intent === 'vai_chover' && /amanh[ãa]/.test(_sbNorm(texto)) && !mH) params.horas = 48;
  const mEui = texto.match(/\b([0-9a-fA-F]{8,32})\b/);
  if (mEui && ['ligar_irrigador', 'desligar_irrigador', 'ultima_leitura'].includes(intent)) {
    params.device_eui = mEui[1];
  }
  if (/confirmo|pode sim|sim,? pode|pode ligar|pode desligar|autorizo|confirmado/i.test(texto)) {
    params.confirm = true;
  }
  if (['associar_tarefa', 'concluir_tarefa'].includes(intent)) {
    const resto = texto
      .replace(
        /^(associe|agende|cri\w+|adicione|adicionar|manda|marque|bota|coloca|conclu[ií]|marcar como feita|finalizar|cancela|cancelar)\s+(uma\s+)?(tarefa\s*(de|para)?)?\s*/i,
        ''
      )
      .trim();
    if (resto) params.titulo = resto.slice(0, 100);
    if (intent === 'associar_tarefa') {
      try {
        const dr = wizDataRelativa(texto);
        if (dr) params.data = dr;
      } catch {}
    }
  }
  if (intent === 'consultar_estoque') {
    const mItem = texto.match(
      /(?:tem|estoque(?: de)?|sobre(?: o| a)?)\s+(.+?)(?:\s+no estoque)?[?.!]*$/i
    );
    if (mItem && mItem[1].length > 1) params.item = mItem[1].slice(0, 60);
  }
  if (intent === 'listar_funcionarios') {
    const mSet =
      texto.match(/(?:setor|cargo|funcao|função|area|área)\s+(?:de\s+|do\s+|da\s+)?([a-zà-ú]+)/i) ||
      texto.match(
        /(mecanicos?|eletricistas?|tratoristas?|soldadores?|operadores?|ruricolas?|diaristas?|administrativos?|gerentes?|capatazes?|borracheiros?)/i
      );
    if (mSet) params.setor = mSet[1];
  }
  if (intent === 'feedback') {
    params.texto = texto;
    if (window._lastExec) params.execucao_id = window._lastExec;
  }
  return params;
}

export function interpretarComandoRecurso(texto) {
  const t = texto.trim();
  if (/^status (do )?copiloto$/i.test(t)) return { intent: 'copiloto_status', params: {} };
  if (/^avalie (a )?propriedade agora$/i.test(t)) return { intent: 'avaliar_cenario', params: {} };
  const ativacao = /^(ative|desative) copiloto propriedade\s+#?(\d+)$/i.exec(t);
  if (ativacao)
    return {
      intent: 'ligar_proatividade',
      params: { propriedade_id: Number(ativacao[2]), ativo: /^ative$/i.test(ativacao[1]) },
    };
  if (/^(liste|listar|mostre) (os )?recursos( do sistema)?$/i.test(t)) {
    return { intent: 'recursos_catalogo', params: {} };
  }
  let m = /^(?:campos|campos de|campos do recurso)\s+([a-z0-9-]+)$/i.exec(t);
  if (m) return { intent: 'recursos_catalogo', params: { recurso: m[1].toLowerCase() } };
  m =
    /^(liste|listar|leia|ler|edite|editar|exclua|excluir)\s+recurso\s+([a-z0-9-]+)(?:\s+#?(\d+))?(?:\s+campos\s+(\{[\s\S]*\}))?$/i.exec(
      t
    );
  if (!m) return null;
  const params = { recurso: m[2].toLowerCase() };
  if (m[3]) params.id = Number(m[3]);
  if (/^(edite|editar|exclua|excluir)$/i.test(m[1])) {
    if (!params.id) return null;
    params.operacao = /^edi/i.test(m[1]) ? 'editar' : 'excluir';
    if (params.operacao === 'editar') {
      if (!m[4]) return null;
      try {
        params.campos = JSON.parse(m[4]);
      } catch {
        return null;
      }
    }
    return { intent: 'recurso_alterar', params };
  }
  return { intent: 'recurso_ler', params };
}

export function interpretarComandoWidget(texto) {
  // Nomes entre aspas mantêm espaços/acentos sem adivinhar a identidade do preset.
  const alvo = /\b(?:preset|dashboard|painel)\s+"([^"]+)"/i.exec(texto);
  if (!alvo || !/\bwidgets?\b/i.test(texto)) return null;
  const tipo = /\bwidget\s+([a-z][a-z0-9-]+)/i.exec(texto)?.[1];
  const params = { preset: alvo[1] };
  if (tipo) params.widget = tipo;
  const normal = _sbNorm(texto);
  if (/^(ler|leia|listar|liste|mostra|mostrar|mostre|ver)\b/.test(normal)) {
    return { intent: 'widget_ler', params };
  }
  if (!tipo) return null;
  if (/^(mova|move|mover)\b/.test(normal)) {
    params.operacao = 'mover';
    const destino = /\bpara\s+(?:o\s+)?(?:preset|dashboard|painel)\s+"([^"]+)"/i.exec(texto);
    if (destino) params.destino = destino[1];
    const posicao = /posi[cç][aã]o\s+(\d+)/i.exec(texto);
    if (posicao) params.posicao = Number(posicao[1]);
    if (!destino && !posicao) return null;
  } else if (/^(exclua|excluir|exclui|apague|apaga|remova|remove)\b/.test(normal)) {
    params.operacao = 'excluir';
  } else if (/^(edite|editar|edita|renomeie|renomear)\b/.test(normal)) {
    params.operacao = 'editar';
    const titulo = /t[ií]tulo\s+"([^"]+)"/i.exec(texto);
    if (titulo) params.titulo = titulo[1];
    const config = /\bconfig\s+(\{[\s\S]*\})\s*$/.exec(texto);
    if (config) {
      try {
        params.config = JSON.parse(config[1]);
      } catch {
        return null;
      }
    }
    if (!titulo && !config) return null;
  } else return null;
  return { intent: 'widget_alterar', params };
}

async function sandboxBridge(texto) {
  if (!window.IASandbox) return null;

  // CONTINUAÇÃO DE ESTADO NO BACKEND (COLETANDO_DADOS, AGUARDANDO_CONFIRMACAO)
  if (window._sbState && window._sbState !== 'NENHUM') {
    try {
      const out = await window.IASandbox.executar(
        window._sbActiveIntent,
        {},
        { entrada: texto, deteccao: { metodo: 'continuacao' } }
      );
      if (out) {
        window._sbState = out.state || 'NENHUM';
        if (window._sbState === 'NENHUM') window._sbActiveIntent = null;
        if (out.execucao_id) window._lastExec = out.execucao_id;
        /* A LISTA DE CAMPOS FICA AQUI, e nao no retorno.
         *
         * Este `return out.resposta` e' o que o dock consome, e uma string não
         * leva a lista com ela. Devolver o objeto inteiro quebraria todos os
         * chamadores que fazem `res.includes(...)` — e o `IA` tem vários.
         * Guardar à parte preserva a assinatura desta função e dá ao painel o
         * que ele precisa para desenhar os campos numerados. */
        window._sbColeta = (out.dados && out.dados.coleta) || null;
        window._sbSerie = (out.dados && out.dados.serie) || null;
        window._sbPeca = (out.dados && out.dados.peca) || null;
        if (out.ok) return out.resposta;
        if (out.needs_confirm) return out.resposta || out.erro || out.pergunta;
        // `pergunta` é o servidor a PEDIR o campo seguinte, não a relatar erro.
        // Handlers de cadastro devolvem `{ok:false, pergunta, campo,
        // needs_confirm:true}` ("Entendi 'operador' como Operador. É isso?").
        // Sem isto a pergunta era deitada fora, `sandboxBridge` devolvia
        // `null`, e a cadeia caía no `analisarIntent` — que respondia outra
        // coisa. O `|| out.pergunta` no ramo de cima é NECESSÁRIO: estes
        // handlers trazem `needs_confirm:true` já no primeiro turno, e sem ele
        // o ramo de baixo nunca era alcançado.
        if (out.pergunta) return out.pergunta;
        if (out.erro) return out.erro;
      }
    } catch (e) {
      console.warn('[IA] sandbox bridge erro na continuacao:', e);
    }
    return null;
  }

  try {
    if (!_sbCatalog) _sbCatalog = await window.IASandbox.intents();
  } catch {
    return null;
  }
  if (!_sbCatalog) return null;
  const t = _sbNorm(texto);
  const has = (...ws) => ws.some((w) => t.includes(_sbNorm(w)));
  let intent = null;
  let forte = false;
  const comandoWidget = interpretarComandoWidget(texto) || interpretarComandoRecurso(texto);
  // trava leitura × escrita também nos fast-paths: pedido de escrita nunca
  // cai em clima/pulverização (ex: "crie tarefa de pulverizar" não é "quando pulverizar")
  // particípios ("cadastrados", "concluída") NÃO são escrita: é consulta ao existente
  const semPart = t.replace(/\b\w+(ados|adas|idos|idas)\b/g, ' ');
  const ehEscrita =
    /(cadastr|cria\w*|crie|registr|adicion|exclu|delet|apag|edit|atualiz|manda|marc|marque)/.test(
      semPart
    );
  const ehPergunta = /\?\s*$/.test(texto.trim());
  // fast-paths: perguntas top (cobrem o console)
  if (comandoWidget) {
    intent = comandoWidget.intent;
    forte = true;
  } else if (has('chover') && !ehEscrita) {
    /* Semana vai para a série (`chuva_semana`, dias×mm para gráfico);
     * hoje/amanhã fica no `vai_chover` em prosa. Sem a divisão, o genérico
     * sequestrava a pergunta semanal — que é a que tem gráfico. */
    if (/(semana|proximos dias|7 dias|sete dias|dia a dia)/.test(t)) {
      intent = 'chuva_semana';
      forte = true;
    } else {
      intent = 'vai_chover';
      forte = true;
    }
  } else if (
    (has('pulveriz') || has('quando aplicar', 'pode aplicar')) &&
    !ehEscrita &&
    !/(responsav|quem)/.test(t)
  ) {
    intent = 'melhor_pulverizar';
    forte = true;
  } else if (has('ligue o irrigador', 'ligar irrig', 'abrir valvula')) {
    intent = 'ligar_irrigador';
    forte = true;
  } else if (has('desligue o irrigador', 'desligar irrig', 'fechar valvula')) {
    intent = 'desligar_irrigador';
    forte = true;
  } else if (
    has('obrigado', 'valeu', 'resolveu', 'perfeito', 'nao gostei', 'errado', 'nao resolveu')
  ) {
    intent = 'feedback';
    forte = true;
  } else if (has('o que voce sabe fazer', 'o que sabe fazer') || texto.trim() === 'ajuda') {
    intent = 'ajuda';
    forte = true;
  } else if (
    has('temperatura', 'qual o clima', 'como esta o tempo', 'como está o tempo') &&
    !ehEscrita
  ) {
    intent = 'clima_agora';
    forte = true;
  }
  if (!intent) {
    // genérico: pontua exemplos do catálogo
    // trava leitura × escrita: pedido de cadastro só casa com intent de ação
    // pergunta (?) prioriza leitura: "terminaram a tarefa?" é status, não escrita
    const stop = new Set(
      'o,a,os,as,um,uma,de,do,da,em,para,que,qual,quais,como,hoje,agora,me,meu,minha,por,favor,tambem,so,ja,ainda,muito,pouco,mais,menos,com,sem,sobre,entre,ate,desde,ontem,quando,onde,quanto,esse,essa,este,esta,isso,isto,ele,ela,seu,sua,nao,sim,ser,estar,ter,fazer,dar,ver,dizer,poder,querer,saber,para,das,dos,pela,pelo,num,numa,esse,essa,temos,tem,fazenda,sao,aqui,nossa,nosso,dela,dele,hoje'.split(
        ','
      )
    );
    const words = t.split(/[^a-z0-9]+/).filter((w) => w.length > 2 && !stop.has(w));
    if (!words.length) return null;
    let best = null,
      bestScore = 0;
    const scores = {};
    for (const [name, spec] of Object.entries(_sbCatalog)) {
      if (ehEscrita) {
        const fl = spec.flags || [];
        if (fl.length && !fl.some((f) => /write|create|comando/.test(String(f)))) continue;
      }
      if (ehPergunta) {
        const fl = spec.flags || [];
        if (fl.some((f) => /write|create/.test(String(f)))) continue;
      }
      let s = 0;
      for (const ex of spec.exemplos || []) {
        const ew = _sbNorm(ex)
          .split(/[^a-z0-9]+/)
          .filter((w) => w.length > 2 && !stop.has(w));
        if (!ew.length) continue;
        // casa exata ou por prefixo (pulveriza≈pulverizar, tarefa≈tarefas; mín 5 letras p/ não inflar "sol/solo")
        s +=
          ew.filter((w) =>
            words.some(
              (u) =>
                u === w || (w.length >= 5 && u.startsWith(w)) || (u.length >= 5 && w.startsWith(u))
            )
          ).length / ew.length;
      }
      scores[name] = Math.round(s * 100) / 100;
      if (s > bestScore) {
        bestScore = s;
        best = name;
      }
    }
    // console: registra COMO a IA entendeu (scores de todos) mesmo sem match
    window._sbScores = scores;
    // O MESMO limiar do servidor. `app/ia/deteccao.py:168` — `LIMIAR = 0.06`.
    //
    // MEDIDO 2026-10-05: aqui estava `0.6`, dez vezes mais estrito. A cadeia de
    // regras explicitas acima (ajuda, clima_agora, ...) cobre os casos comuns, e por
    // baixo o pontuador generico é uma porta do algoritmo do servidor — a mesma
    // lista de `stop`, o mesmo score por sobreposicao de palavras. Com limiares
    // diferentes, a MESMA frase dava intents diferentes conforme se perguntava ao
    // dock do AmplIA (navegador) ou a API.
    //
    // O que 0.6 comprava: recusa de intents fracos. O que custava: frases que o
    // servidor aceita (score 0.06 a 0.6) nunca chegavam a correr no navegador.
    // O servidor e' que tem a medicao — `tests/test_limiar_deteccao.py` guarda a
    // distribuicao, e o comentario de `LIMIAR` diz porque 0.06 e nao 0.10.
    //
    // Um match fraco de LEITURA e' inofensivo. Um de ESCRITA nao passa: o gate de
    // `requires_confirmation` e o M3 (`_LIMIAR_ESCRITA`, 0.6) estao antes da
    // execucao. Por isso baixar o limiar aqui nao abre nenhuma escrita.
    if (best && bestScore >= 0.06) {
      intent = best;
      forte = bestScore >= 1.0;
    }
  }
  if (!intent) {
    // console: entendimento sem match — aparece no registro com o texto de entrada
    try {
      window.IASandbox._log('entendimento', 'sem match: ' + texto.slice(0, 120), {
        entrada: texto,
        scores: window._sbScores || {},
      });
    } catch {}
    return null;
  }
  const deteccao = {
    metodo: forte ? 'fast-path' : 'generico',
    scores: window._sbScores || {},
    escolhido: intent,
  };
  try {
    const out = await window.IASandbox.executar(
      intent,
      comandoWidget?.params || _sbExtrairParams(texto, intent),
      {
        entrada: texto,
        deteccao,
      }
    );
    if (out && out.execucao_id) window._lastExec = out.execucao_id;
    if (out && out.state) {
      window._sbState = out.state;
      if (out.state !== 'NENHUM') window._sbActiveIntent = intent;
      else window._sbActiveIntent = null;
    } else {
      window._sbState = 'NENHUM';
      window._sbActiveIntent = null;
    }
    /* A LISTA DE CAMPOS, no PRIMEIRO pedido tambem.
     *
     * MEDIDO: estava so' na continuacao (aqui em cima), e o primeiro pedido e'
     * onde a IA pergunta o PRIMEIRO campo — que e' a mensagem que o produtor
     * ve. Sem isto aqui, `coleta` ficava `undefined` no turno em que mais
     * importa e a lista nunca aparecia. A lista e' da mesma resposta que
     * produz a pergunta; uma sem a outra e' uma ou outra a meio. */
    window._sbColeta = (out && out.dados && out.dados.coleta) || null;
    window._sbSerie = (out && out.dados && out.dados.serie) || null;
    window._sbPeca = (out && out.dados && out.dados.peca) || null;
    if (out && out.ok) return out.resposta;
    if (out && out.needs_confirm) return out.resposta || out.erro || out.pergunta; // pede confirmação (irrigador)
    if (out && out.pergunta) return out.pergunta; // pergunta de desambiguação do servidor
    if (forte && out && out.erro) return out.erro; // ex: "sem coordenadas" — diz o que falta
    return null;
  } catch {
    return null;
  }
}

/* == REGISTO DE QUEM RESPONDEU ==
 *
 * `iaChat` tem ~20 pontos de captura em cascata. Sem isto, quando o produtor
 * relatava "respondeu a coisa errada", nao havia forma de saber por que caminho
 * a resposta saiu: nenhum dos blocos guardava o seu nome. O produtor via um
 * efeito; ninguem via a causa.
 *
 * `_dec()` devolve o texto E marca quem falou. E um no-op em producao se o
 * `console` nao estiver aberto, e nunca muda o que o produtor ve.
 */
const IA_DECISOES = { turno: 0, ultima: null, ms: 0, historico: [] };

/* == A1-b: O CONTEXTO DA PROPRIEDADE, SEM UM `fetch` POR MENSAGEM ==
 *
 * Antes, dentro do bloco "PROTOCOLO ABSOLUTO", havia um
 * `fetch('/api/propriedades/')` a CADA mensagem, sem timeout e sem cache.
 * Em campo isso e o pior sitio possivel para uma chamada de rede:
 *
 *   1. Sem rede, o `.catch(() => null)` devolvia `{}` — e `{}` MENTE. Diz que a
 *      propriedade nao existe. O agente passou a trabalhar com `cidade: ''` e
 *      `uf: ''`, perdia o contexto, e caia nos decisores de baixo — os que
 *      fabricam (ver A3). Esta era a hipotese mais provavel para o "esquece".
 *   2. A chamada nao tinha timeout: em rede de baixa o `fetch` podia ficar
 *      pendurado, e o produtor via o agente "a pensar" sem resposta.
 *
 * Agora: cache de 60 s, timeout de 2.5 s, e devolve `null` (nao sei) em vez de
 * `{}` (nao existe). O `null` e o que permite ao `iaChat` marcar `semContexto`.
 */
/* `_ctxProp`, e nao `_ctxCache`: ja existe um `_ctxCache` em `entenderSistema()`
 * (a 4463), que cacheia a DESCRICAO do sistema. Nao e o mesmo dado e nao pode
 * partir a mesma variavel. */
let _ctxProp = { t: 0, valor: null };
const IA_CTX_TTL_MS = 60000;
const IA_CTX_TIMEOUT_MS = 2500;

async function contextoPropriedade() {
  const agora = (() => {
    try {
      return Date.now();
    } catch {
      return 0;
    }
  })();
  if (_ctxProp.valor && agora - _ctxProp.t < IA_CTX_TTL_MS) return _ctxProp.valor;
  try {
    const ctrl = typeof AbortController !== 'undefined' ? new AbortController() : null;
    const timer = ctrl ? setTimeout(() => ctrl.abort(), IA_CTX_TIMEOUT_MS) : null;
    const r = await fetch('/api/propriedades/', ctrl ? { signal: ctrl.signal } : undefined);
    if (timer) clearTimeout(timer);
    const v = (r.ok ? await r.json() : null)?.results?.[0];
    if (v) _ctxProp = { t: agora, valor: v };
    return v || _ctxProp.valor || null;
  } catch {
    return _ctxProp.valor || null;
  }
}

/** Esvazia o cache do contexto. `iaReset()` chama, e quando muda de propriedade. */
export function iaLimparContexto() {
  _ctxProp = { t: 0, valor: null };
}

/* == A2: O AGENTE NAO TEM CONCEITO DE INTERROMPER ==
 *
 * Havia ~11 maquinas de estado concorrentes: `iaCadastroPendente` (um slot
 * unico) mais um global por wizard (wizSafra, wizAnimal, wizAqua, wizTalhao,
 * wizVinc, wizFunc, wizFuncRem, wizTarefa, wizTarCancel, wizLoteQ). Todas vivas
 * ao mesmo tempo, sem nocao de qual esta em FOCO agora.
 *
 * O que o produtor vivia: comeca um cadastro de safra, recebe "nome da safra?",
 * e antes de responder diz "vai chover?". O `wizSafra` estava ativo, portanto a
 * cascata do `iaChat` o interceptava ANTES do LLM e tratava "vai chover?" como
 * resposta a "nome da safra?" — e gravava isso como nome. O produtor nao recebia
 * a previsao, nao havia aviso, e nao havia forma de saber o que tinha acontecido.
 *
 * Nao reescrevi os wizards (o ficheiro esta a ser editado noutro sitio). Isto da
 * ao `iaChat` uma unica nocao: qual fluxo esta em FOCO, e que uma frase de
 * interrupcao o pausa sem lhe roubar a mensagem.
 */
const IA_FOCO = { fluxo: null, desde: 0, pausado: null };

function iaFocoToma(fluxo) {
  IA_FOCO.fluxo = fluxo;
  IA_FOCO.desde = Date.now();
}
function iaFocoSolta(fluxo) {
  if (!fluxo || IA_FOCO.fluxo === fluxo) {
    IA_FOCO.fluxo = null;
    IA_FOCO.desde = 0;
  }
}
function iaFocoTem() {
  return !!IA_FOCO.fluxo;
}

/* Frases que o produtor usa para interromper um fluxo. Deliberadamente curtas e
 * explicitas: uma deteção demasiado generosa ("para") ia roubar respostas
 * legítimas do proprio cadastro ("para a safra 2026"). */
const IA_INTERROMPE =
  /^(desculpa|e\s+a\s+i\b|para\s+(a\s+)?ia\b|cancela|cancelar|deixa\s+(isso|disso)|muda\s+de\s+assunto|troca\s+de\s+assunto|espera\s+ai\b|pausa\b)/i;

/** Interrompe o fluxo em foco, se a mensagem for uma interrupcao. */
function iaFocoInterrompido(texto) {
  if (!iaFocoTem()) return null;
  const t = String(texto || '').trim();
  if (!t || !IA_INTERROMPE.test(t)) return null;
  const quem = IA_FOCO.fluxo;
  iaFocoSolta(quem);
  // Guarda-se o que estava a ser escrito. Perder o progresso e o que faz a
  // pessoa desistir e nunca mais tentar.
  IA_FOCO.pausado = { fluxo: quem, t: Date.now() };
  try {
    sessionStorage.setItem('ia_wiz_pausado', JSON.stringify(IA_FOCO.pausado));
  } catch {}
  return _dec(
    'interrupcao',
    `Parei o cadastro de ${quem}. O que ja tinha respondido fica guardado — é só dizer "voltar".`
  );
}

/** Retoma um fluxo pausado, se existir. */
export function iaFocoRetomar() {
  let p = IA_FOCO.pausado;
  try {
    if (!p) p = JSON.parse(sessionStorage.getItem('ia_wiz_pausado') || 'null');
  } catch {}
  if (!p || !p.fluxo) return null;
  iaFocoToma(p.fluxo);
  IA_FOCO.pausado = null;
  try {
    sessionStorage.removeItem('ia_wiz_pausado');
  } catch {}
  return _dec('retomar', `Voltando ao cadastro de ${p.fluxo}.`);
}

function _dec(decisor, texto) {
  IA_DECISOES.turno += 1;
  IA_DECISOES.ultima = decisor;
  IA_DECISOES.historico.push(decisor);
  // Janela: um turno de campo pode ser longo e nao interessa a lista toda.
  if (IA_DECISOES.historico.length > 40) IA_DECISOES.historico.shift();
  try {
    console.info(`[IA] turno ${IA_DECISOES.turno} <- decisor: ${decisor} (${IA_DECISOES.ms}ms)`);
  } catch {}
  return texto;
}

async function iaChat(msgs, onChunk) {
  const lastUser = msgs[msgs.length - 1]?.content || '';
  const _t0 = (() => {
    try {
      return performance.now();
    } catch {
      return 0;
    }
  })();

  /* == A2: INTERRUPCAO, ANTES DE TUDO ==
   *
   * Este bloco tem de vir ANTES da cascata. Se vier depois, e tarde: os wizards
   * em curso ja capturaram a mensagem e a tratam como campo do cadastro — que
   * e exatamente o defeito que se quer corrigir. */
  const interrompido = iaFocoInterrompido(lastUser);
  if (interrompido) return interrompido;
  if (/^\s*(voltar|retomar|continuar)\b/i.test(lastUser)) {
    const retomado = iaFocoRetomar();
    if (retomado) return retomado;
  }

  // ══ WIZARDS GUIADOS: fluxo contínuo tem prioridade total ══
  try {
    if (typeof wizSafra !== 'undefined' && wizSafra) {
      return _dec('wizSafra', await wizSafraStep(lastUser));
    }
    if (typeof wizAnimal !== 'undefined' && wizAnimal) {
      return _dec('wizAnimal', await wizAnimalStep(lastUser));
    }
    if (typeof wizAqua !== 'undefined' && wizAqua) {
      return _dec('wizAqua', await wizAquaStep(lastUser));
    }
    if (typeof wizTalhaoF !== 'undefined' && wizTalhaoF) {
      return _dec('wizTalhao', await wizTalhaoStep(lastUser));
    }
    if (typeof wizVinc !== 'undefined' && wizVinc) {
      return _dec('wizVinc', await wizVincStep(lastUser));
    }
    if (typeof wizFunc !== 'undefined' && wizFunc) {
      return _dec('wizFunc', await wizFuncStep(lastUser));
    }
    if (typeof wizFuncRem !== 'undefined' && wizFuncRem) {
      return _dec('wizFuncRem', await wizFuncRemStep(lastUser));
    }
    if (typeof wizTarefa !== 'undefined' && wizTarefa) {
      return _dec('wizTarefa', await wizTarefaStep(lastUser));
    }
    if (typeof wizTarCancel !== 'undefined' && wizTarCancel) {
      return _dec('wizTarCancel', await wizTarCancelStep(lastUser));
    }
    if (typeof wizLoteQ !== 'undefined' && wizLoteQ) {
      const n = wizNorm(lastUser);
      if (/peixe|aquatico|tanque|viveiro|despesca|camarao|tilapia|tambaqui/.test(n)) {
        wizLoteQ = false;
        return _dec('wizLote->aqua', wizAquaStart());
      }
      if (
        /boi|vaca|gado|rebanho|animal|suino|porco|ovino|caprino|equino|cavalo|frango|galinha|leite|ovos|piquete|coelho/.test(
          n
        )
      ) {
        wizLoteQ = false;
        return _dec('wizLote->animal', wizAnimalStart());
      }
      if (/safra|plantio|cultivo|plantar/.test(n)) {
        wizLoteQ = false;
        return _dec('wizLote->safra', wizSafraStart(typeof t !== 'undefined' ? t : lastUser));
      }
      return _dec('wizLote(pergunta)', 'Lote de quê? 🌱 safra/plantio, 🐄 rebanho ou 🐟 peixe?');
    }
    if (typeof wizAquaTrigger === 'function' && wizAquaTrigger(lastUser)) {
      return _dec('wizAquaTrigger', wizAquaStart());
    }
    if (typeof wizAnimalTrigger === 'function' && wizAnimalTrigger(lastUser)) {
      return _dec('wizAnimalTrigger', wizAnimalStart());
    }
    if (typeof wizTrigger === 'function' && wizTrigger(lastUser)) {
      return _dec('wizTrigger', wizSafraStart(typeof t !== 'undefined' ? t : lastUser));
    }
    if (typeof wizVincTrigger === 'function' && wizVincTrigger(lastUser)) {
      const s = wizVincStart(lastUser);
      try {
        const pre = await wizVincPrefill(lastUser);
        if (pre.cultura) {
          wizVinc.cultura = pre.cultura;
          wizVinc._tentouPre = true;
          if (pre.talhao) {
            wizVinc.talhao = pre.talhao;
            wizVinc.step = 'conf';
            return _dec(
              'wizVinc(pre)',
              `Entendi: ${pre.cultura.nome} no talhão ${pre.talhao.nome}. Confirmo? (sim/não)`
            );
          }
          wizVinc.step = 'talhao';
          return _dec('wizVinc(pre)', `Cultura: ${pre.cultura.nome}. Em qual talhão?`);
        }
      } catch {}
      return _dec('wizVinc', s);
    }
    if (typeof wizTalhaoTrigger === 'function' && wizTalhaoTrigger(lastUser)) {
      return _dec('wizTalhaoTrigger', wizTalhaoStart(lastUser));
    }
    if (typeof wizFuncRemTrigger === 'function' && wizFuncRemTrigger(lastUser)) {
      return _dec('wizFuncRemTrigger', wizFuncRemStart(lastUser));
    }
    if (typeof wizFuncTrigger === 'function' && wizFuncTrigger(lastUser)) {
      return _dec('wizFuncTrigger', wizFuncStart(lastUser));
    }
    if (typeof wizTarCancelTrigger === 'function' && wizTarCancelTrigger(lastUser)) {
      const s = wizTarCancelStart();
      if (s === '__LISTAR__') return _dec('wizTarCancelTrigger', await wizTarCancelStep(''));
      return _dec('wizTarCancelTrigger', s);
    }
    if (typeof wizTarefaTrigger === 'function' && wizTarefaTrigger(lastUser)) {
      return _dec('wizTarefaTrigger', wizTarefaStart(lastUser));
    }
    if (typeof wizLoteAmbiguo === 'function' && wizLoteAmbiguo(lastUser)) {
      wizLoteQ = true;
      return _dec('wizLoteAmbiguo', 'Lote de quê? 🌱 safra/plantio, 🐄 rebanho ou 🐟 peixe?');
    }
  } catch (e) {
    console.warn('[IA] wizard erro:', e);
  }
  // RACIOCINIO LOCAL PRIMEIRO: o modelo local entende duvidas, perguntas
  // compostas e pedidos ambiguos — que e o que o regex nao sabe. Os wizards
  // acima continuam antes, porque sao maquinas de estado em curso.
  if (iaEngine && iaReady !== 'server') {
    try {
      const r = await raciocinarLlm({ lastUser, msgs, onChunk });
      if (r) return r;
    } catch (e) {
      console.warn(
        '[IA] raciocinio local falhou, caindo no modo regras (primeira versão):',
        e && e.message
      );
    }
  }

  // ══ PONTE SANDBOX primeiro: 19 intents do servidor antes do regex local ══
  try {
    const sb = await sandboxBridge(lastUser);
    if (sb) return sb;
  } catch (e) {
    console.warn('[IA] sandbox bridge erro:', e);
  }
  // wizard pendente tem prioridade - trata resposta como preenchimento
  if (iaCadastroPendente) {
    const avancou = avancarCadastro(lastUser);
    if (typeof avancou === 'string') return avancou;
    if (avancou && avancou.finalizar) {
      try {
        const url = RECURSOS_API[avancou.recurso] || `/api/${avancou.recurso}/`;
        const created = await apiFetch(url, {
          method: 'POST',
          body: JSON.stringify(avancou.dados),
        });
        const nome = created?.nome || created?.titulo || created?.id || '';
        return _dec(
          'iaCadastroPendente',
          `✅ ${avancou.recurso} criado com sucesso!${nome ? ' — ' + nome : ''}`
        );
      } catch (e) {
        return _dec('iaCadastroPendente(erro)', `Erro ao criar ${avancou.recurso}: ${e.message}`);
      }
    }
  }

  // ══ 0) PROTOCOLO ABSOLUTO — analisar intenção, verificar dados reais, perguntar se faltar ══
  try {
    /* Ver A1-b: `contextoPropriedade()` tem cache e timeout. Antes era um
     * `fetch('/api/propriedades/')` a CADA mensagem, dentro da decisão. */
    const prop = await contextoPropriedade();
    const ctx = {
      propriedade: prop || {},
      estacoes: prop?.estacoes || [],
      cidade: prop?.cidade || '',
      uf: prop?.uf || '',
      /* O sinal honesto: `propriedade: {}` e um objeto VAZIO que mente — diz que a
       * propriedade nao existe. `semContexto` diz a verdade: nao se soube ler.
       * Sem esta distincao o agente passa a inventar em campo. */
      semContexto: !prop,
    };
    const intent = analisarIntent(lastUser, ctx);
    /* == (a) A CORRECÇÃO QUE FECHA O FLUXO DA ESTAÇÃO ==
     *
     * A pergunta "(a) Cadastrar estação?" era seguida de "Nome da estação?",
     * e a conversa morria ali. A razão era esta, e só esta:
     *
     * `analisarIntent('a')` devolve `tipo:'criar'`, `acao:'estacoes'` e
     * `falta:['nome','latitude','longitude']`. Com `falta` preenchida, o `if`
     * logo abaixo disparava e devolvia `intent.pergunta` — a STRING. O
     * `smartResponse` nunca era alcançado com o cadastro aberto, e
     * `iaCadastroPendente` continuava `null`. Nunca houve cadastro a receber
     * a resposta seguinte.
     *
     * A pessoa escrevia "estaçao met do lucas", e essa mensagem não é
     * reconhecível como campo de nada: não há nome de campo nela, e nenhuma
     * máquina de estado à espera. Daí o "Entendi sua mensagem" — a resposta
     * honesta do sistema a uma frase que ele nunca tinha pedido.
     *
     * `criar` é o ÚNICO tipo que pede um dado para GUARDAR, e por isso o
     * único que tem de abrir a máquina de estado ANTES de perguntar. Imprimir
     * a pergunta sem abrir o cadastro é o pedido de um campo que ninguém vai
     * receber — e é a única forma de este fluxo morrer.
     *
     * Fica ANTES do `if` de `falta` porque esse bloco consome `criar` e nunca
     * o deixaria chegar aqui. */
    if (intent.tipo === 'criar' && intent.acao && ESQUEMAS_CADASTRO[intent.acao]) {
      // Não se abre um cadastro por cima de outro: quem está no meio de um
      // cadastro tem direito a acabar ou a cancelar, não a ser sequestrado
      // por uma pergunta nova.
      if (iaCadastroPendente) {
        return _dec(
          'analisarIntent(criar:emCurso)',
          `Está no meio de um cadastro de ${iaCadastroPendente.recurso} (${iaCadastroPendente.etapa}/${iaCadastroPendente.esquema.length}). Diga "cancelar" para sair ou responda à pergunta actual.`
        );
      }
      return _dec('analisarIntent(criar)', iniciarCadastro(intent.acao));
    }
    // Se falta informação e não é wizard pendente → pergunta adaptativa (não inventa)
    if (intent.falta && intent.falta.length > 0 && !iaCadastroPendente) {
      const pergunta = perguntarSequencial(
        intent.pergunta || 'Preciso confirmar: ' + intent.falta.join(', '),
        ctx
      );
      // ESTE RAMO DE CLIMA FOI REMOVIDO, e não por estilo: com a pergunta que o
      // produzia também removida, ele nunca mais dispara.
      //
      // `analisarIntent` só punha `falta: ['estacao_meteorologica_ou_web']`
      // quando `!temEstacao && !temChaveOWM` — e as DUAS condições eram
      // sempre falsas. `ctx.estacoes` vinha de `prop.estacoes`, campo que
      // `PropriedadeSerializer` não tem (a relação chama-se
      // `estacoes_meteo`); e `window.OPENWEATHER_API_KEY` nunca existiu no
      // browser, porque a chave vive em `settings.py`. Uma condição com duas
      // partes que nunca são verdade é uma tautologia: o agente perguntava de
      // onde queria o tempo em TODA pergunta de clima, e nunca consultava a
      // previsão — que era o que o produtor tinha pedido.
      //
      // A pergunta não se perde: passa a ser a resposta de `buscarClimaWeb`,
      // que vai à fonte real e, se ela calar, diz o motivo que o servidor deu.
      // Se é pesquisa por bovino (leite+corte) → confirma tipo
      if (intent.acao === 'animais' && intent.falta.includes('tipo_producao')) {
        return _dec(
          'analisarIntent(animais)',
          `🐄 Confirmando: você quer dados de bovinos de corte, leite, misto ou todos? E quer consultar por brinco, piquete, peso ou produção?`
        );
      }
      // Se é IoT / telemetria → confirma sensor / talhão
      if (intent.acao === 'sensores' || intent.acao === 'telemetria') {
        return _dec(
          'analisarIntent(iot)',
          `📡 Qual sensor? (temperatura, umidade_solo, chuva, vento, nível) E qual talhão/propriedade?`
        );
      }
      // Se é edição / criação / consulta genérica → pergunta contexto
      return _dec('analisarIntent(pergunta)', perguntarSequencial(pergunta, ctx));
    }
    // Se é consulta com dados reais → prossegue para smartResponse (já confirmada)
  } catch (e) {
    console.warn('[IA] protocolo erro:', e);
  }

  // ══ 1) SMART RESPONSE — consulta API real e responde com dados verdadeiros ══
  try {
    const smart = await smartResponse(lastUser);
    if (smart) return _dec('smartResponse', smart);
  } catch (e) {
    console.warn('[IA] smartResponse erro:', e);
  }

  // ══ 2) FALLBACK INTENT — detecta intenção por regex e executa tool ══
  const fb = fallbackIntent(lastUser);
  if (fb) {
    // Se é JSON de tool, executa silenciosamente e retorna resultado humanizado
    if (fb.trim().startsWith('{') && fb.includes('"tool"')) {
      try {
        const toolRes = await toolCallGovernada(fb, lastUser);
        if (toolRes) return _dec('fallback(tool)', sanitizarResposta(toolRes));
      } catch {}
    }
    return _dec('fallback(texto)', sanitizarResposta(fb));
  }

  // ══ 4) Fallback final — resposta local honesta (sem endpoint morto) ══
  try {
    IA_DECISOES.ms = Math.round(performance.now() - _t0);
  } catch {}
  return _dec(
    'fallbackFinal',
    'Não consegui processar agora. Tente de novo com uma pergunta mais curta, ou use o painel: "qual minha produção total", "mostrar estoque", "vai chover?".'
  );
}

/* Os NOMES LEGADOS que levam a uma acção que muda dados.
 *
 * A lista existiu para o modelo antigo saber o que escrever. Havia treze
 * nomes, e as ferramentas que eles apontavam não existiam — por isso o modelo
 * escrevia `{"tool":"irrigacao",...}` e o servidor devolvia
 * `tool_fora_do_catalogo` a todas. (FILA #27.)
 *
 * O que este mapa faz não é ensinar o modelo: é o caminho de RECUPERAÇÃO. O
 * `toolCallGovernada` normaliza o prefixo `amplia_`, e o servidor devolve
 * `sugestoes` quando o nome não existe. O modelo que tentar um nome antigo
 * chega aqui, recebe o nome verdadeiro, e a chamada seguinte passa.
 *
 * `irrigacao` precisa de uma tabela porque o nome antigo não distinguia
 * ligar de desligar — e são acções físicas diferentes. A `acao` é que diz
 * qual, e só o produtor decide se avançam.
 */
const ACAO_IRRIGACAO = {
  ligar: 'amplia_ligar_irrigador',
  desligar: 'amplia_desligar_irrigador',
  on: 'amplia_ligar_irrigador',
  off: 'amplia_desligar_irrigador',
};

async function iaToolCall(text) {
  /* O que sobrou daqui, e porque é que é tão pouco.
   *
   * Esta função JÁ FOI "desligada" uma vez, pelo BUILD 0 — e mesmo assim
   * continuava a escrever. O comentário dizia que as chamadas remanescentes
   * caíam "numa régua legada, que é só leitura", e o código tinha seis
   * chamadas a escrever e duas a acionar uma válvula de irrigação. Um
   * comentário que descreve o código não o governa.
   *
   * MEDIDO, L2, o que esta função fazia por baixo do "DESLIGADA":
   *   POST   /api/iot/comandos/   x2  <- acção física, sem confirm, sem auditoria
   *   POST   /api/<recurso>/      x1  <- criava registos
   *   PATCH  /api/<recurso>/<id>/ x1
   *   DELETE /api/<recurso>/<id>/ x1
   *   POST   /api/relatorio/gerar/ x1
   * E o ramo de irrigação nem escolhia o dispositivo: mandava
   * `device: lista[0]?.id || 1`.
   *
   * O que fica agora:
   *   - navegação (mudar o endereço) — não muda dados;
   *   - leitura de recurso (GET) — não muda dados;
   *   - busca externa — o POST é transporte da pergunta, não uma escrita;
   *   - o wizard de cadastro local (estado da aba, não do servidor).
   *
   * Qualquer acção que mude dados passa por `toolCallGovernada`, que vai a
   * `/api/amplia/exec/` e dai a `sandbox.executar`: `needs_confirm`, flag de
   * capacidade e linha em `IAExecucao`. Um caminho só, e é este.
   */
  console.warn('[IA] iaToolCall: acoes que mudam dados vao pela porta governada.');

  let j = null;
  try {
    const m = text.match(/\{[^]*"tool"[^]*\}/);
    if (m) j = JSON.parse(m[0]);
  } catch (e) {
    console.warn('tool parse', e);
    return null;
  }
  if (!j || !j.tool) return null;
  const tool = j.tool;
  const a = j.args || {};
  try {
    if (tool === 'iniciar_cadastro') {
      const msg = iniciarCadastro(a.recurso);
      return msg;
    }
    if (tool === 'cancelar_cadastro') {
      iaCadastroPendente = null;
      return 'Cadastro cancelado.';
    }

    /* Irrigação: acção física, e por isso a que devia mesmo ter confirmação.
     * Deixa de ser um POST directo e passa a ser o intent governado. O
     * `confirm` NÃO é posto aqui: quem o posta é o produtor, e é o servidor
     * que recusa sem ele — que é o que fecha a FILA #32. */
    if (tool === 'irrigacao') {
      const acao = String(a.acao || 'ligar').toLowerCase();
      const nome = ACAO_IRRIGACAO[acao];
      if (!nome) {
        return `Não sei ${acao} a irrigação. Só sei ligar ou desligar.`;
      }
      return await toolCallGovernada(
        JSON.stringify({ tool: nome, args: a.talhao ? { talhao: a.talhao } : {} }),
        a.talhao ? `irrigação ${acao} — talhão ${a.talhao}` : `irrigação ${acao}`
      );
    }

    /* As escritas que aqui estavam (`criar`, `atualizar`, `excluir`,
     * `criar_operacao`) saem pela porta governada. Não há tradução para os
     * intents do catálogo: `criar` não é um intent, e inventar um intent
     * genérico de escrita seria devolver ao modelo uma lâmina sem
     * confirmação — que é o defeito outra vez, com nome novo. O que fica é a
     * recusa honesta, que diz o que fazer em vez de fingir que consegue. */
    if (tool === 'criar' || tool === 'criar_cadastro' || tool === 'criar_operacao') {
      return (
        'Criar registos pela conversa passou a ser pelo cadastro guiado, que ' +
        'pede um campo de cada vez e confirma no fim. Diga ' +
        '"cadastrar safra" ou "cadastrar funcionário" e eu sigo o passo a passo.'
      );
    }
    if (tool === 'atualizar') {
      return (
        'Não actualizo registos sem saber qual. Diga o que quer mudar e em qual ' +
        'cadastro, e eu confirmo antes de gravar.'
      );
    }
    if (tool === 'excluir' || tool === 'deletar') {
      return 'Não apago nada a partir da conversa. Apague pelo painel, onde vê o registo antes de o perder.';
    }
    if (tool === 'consultar' || tool === 'buscar_dados' || tool === 'ler_dados') {
      let recurso = (a.recurso || '').toLowerCase();
      // aliases
      const alias = {
        safras: 'safras',
        safra: 'safras',
        talhoes: 'talhoes',
        talhao: 'talhoes',
        estoque: 'estoque',
        financeiro: 'lancamentos',
        lancamentos: 'lancamentos',
        funcionarios: 'funcionarios',
        maquinarios: 'maquinarios',
        sensores: 'sensores',
        operacoes: 'operacoes',
        agenda: 'operacoes',
        culturas: 'culturas',
        propriedades: 'propriedades',
        insumos: 'insumos',
        animais: 'animais',
      };
      recurso = alias[recurso] || recurso;
      let url = RECURSOS_API[recurso];
      if (!url) {
        // tenta endpoints de dados
        const dataMap = {
          dashboard: '/api/dashboard/',
          financeiro: '/api/financeiro/',
          gestao: '/api/gestao/',
          sensores: '/api/sensores/',
          dispositivos: '/api/dispositivos/',
          notificacoes: '/api/notificacoes/',
          agenda: '/api/agenda/',
          pecuaria: '/api/pecuaria/',
          estoque_data: '/api/estoque/',
        };
        url = dataMap[recurso] || `/api/${recurso}/`;
      }
      if (a.id) url += `${a.id}/`;
      if (a.filtros) {
        // traduz filtros especiais
        if (a.filtros.hoje) {
          a.filtros.data_agendada = new Date().toISOString().slice(0, 10);
          delete a.filtros.hoje;
        }
        if (a.filtros.produto) {
          // commodities espera ?produto=soja
          a.filtros.cultura = a.filtros.produto;
        }
        const qs = new URLSearchParams(a.filtros).toString();
        if (qs) url += `?${qs}`;
      }
      const data = await apiFetch(url);
      // formatação natural — nunca JSON bruto
      return formatarDadosNatural(recurso, data);
    }
    /* `criar`, `atualizar`, `excluir` e `relatorio` não têm ramo aqui.
     *
     * Estão tratados no topo da função, e o que fazem é recusar com o caminho
     * certo. Deixar um segundo ramo adiante seria duas respostas para a mesma
     * palavra — e a segunda, silenciosamente, ainda gravaria.
     *
     * A regra que fecha a FILA #32, e que vale mais do que este ficheiro: um
     * caminho de escrita que não passa por `sandbox.executar` não é uma
     * herança, é um buraco. Não se desliga com um comentário.
     */
    if (tool === 'buscar_web') {
      if (!navigator.onLine) return 'No momento a busca externa está indisponível.';
      const r = await apiFetch('/api/ia/web-search/', {
        method: 'POST',
        body: JSON.stringify({ q: a.q }),
      });
      return r.snippets?.map((s) => s.title + ': ' + s.snippet).join('\n') || 'sem resultado';
    }
  } catch (e) {
    console.warn('tool exec', e);
    const msg = e.message || '';
    if (msg.includes('<!DOCTYPE') || msg.includes('AssertionError') || msg.includes('HTTP 500')) {
      return `Não consegui buscar ${
        a.recurso || tool
      } no momento. Tente novamente ou verifique em ${PAGINAS[a.recurso] || '/'} .`;
    }
    return `Erro ao executar ${tool}: ${msg.slice(0, 400)}`;
  }
  return null;
}

/* Uma sessão de voz de cada vez. `_recVoz` é nomeado de propósito: sem isto,
 * cada clique no botão criava um `SpeechRecognition` novo e NENHUM era parado —
 * `ia_dock.html` ignorava o valor devolvido, portanto não havia caminho para
 * `r.stop()`. Cinco cliques deixavam cinco microfones abertos, todos a
 * disparar `iaDockSend()` sobre a mesma frase. */
let _recVoz = null;

function iaVoz(onText) {
  const R = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!R) {
    alert('Voz não suportada neste navegador');
    return null;
  }

  // Uma sessão de cada vez: a anterior é parada antes de abrir a nova.
  iaVozStop();

  const r = new R();
  r.lang = 'pt-BR';
  r.interimResults = false;
  r.maxAlternatives = 1;

  r.onresult = (e) => {
    /* O ÚLTIMO resultado, não o primeiro.
     *
     * `e.results` é uma lista ACUMULADA durante toda a sessão de reconhecimento.
     * `e.results[0][0]` devolvia, para sempre, a PRIMEIRA frase dita nessa
     * sessão — que é exatamente o "loop" que o produtor relatava: ele dizia uma
     * coisa e a IA repetia aquilo sem ele voltar a falar. Não era o modelo a
     * prender-se; era o índice. */
    const res = e.results[e.results.length - 1];
    if (!res || !res[0]) return;
    const t = res[0].transcript;
    if (t && String(t).trim() && onText) onText(String(t).trim());
  };

  r.onerror = (e) => {
    console.warn('[IA] voz', e && e.error);
    /* Falha de microfone NÃO pode ficar em silêncio: o `console.warn` engolia o
     * erro e o produtor ficava sem saber se o agente ainda ouvia. */
    if (e && e.error === 'not-allowed' && onText) onText('__erro_microfone__');
  };

  /* Sem isto, o fim do reconhecimento não era tratado: o objeto ficava vivo e
   * o próximo `onresult` continuava a disparar envios. */
  r.onend = () => {
    if (_recVoz === r) _recVoz = null;
  };

  _recVoz = r;
  r.start();
  return r; // quem chama TEM de poder parar — `iaReset` e o botão usam isto
}

/** Parar a voz. Chamar de `iaReset()` e de qualquer botão de parar. */
export function iaVozStop() {
  if (!_recVoz) return;
  try {
    _recVoz.onresult = null;
    _recVoz.stop();
  } catch {}
  _recVoz = null;
}

// Zera a conversa: cancela wizards/fluxos em andamento (limpa dados parciais),
// descarta scores da última detecção, histórico persistido e fala em curso.
// NÃO apaga dados já salvos no servidor (safras, tarefas concluídas etc.).
function iaReset() {
  /* A2: o foco de fluxo tambem tem de cair, ou o `iaChat` continuaria a
   * achar que ha um cadastro em curso depois de "zerar conversa". */
  iaFocoSolta(null);
  IA_FOCO.pausado = null;
  try {
    sessionStorage.removeItem('ia_wiz_pausado');
  } catch {}
  /* A8: a voz tambem. Sem isto, o microfone continuava aberto depois de zerar. */
  try {
    iaVozStop();
  } catch {}
  /* A1-b: o contexto da propriedade tambem. */
  try {
    iaLimparContexto();
  } catch {}
  try {
    if (window.iaLocal && typeof window.iaLocal.limparWizard === 'function') {
      window.iaLocal.limparWizard();
    }
  } catch {}
  try {
    iaCadastroPendente = null;
    wizSafra = null;
    wizAnimal = null;
    wizAqua = null;
    wizLoteQ = false;
    wizSwitch = null;
    wizTalhaoF = null;
    wizVinc = null;
    wizFunc = null;
    wizFuncRem = null;
    wizTarefa = null;
    wizTarCancel = null;
  } catch {}
  try {
    window._sbScores = {};
  } catch {}
  try {
    localStorage.removeItem('amplia_ia_hist');
  } catch {}
  try {
    if ('speechSynthesis' in window) speechSynthesis.cancel();
  } catch {}
}
window.iaLocal = {
  iaInit,
  iaChat,
  iaToolCall,
  iaVoz,
  entenderSistema,
  iaReset,
  limparWizard: () => {
    iaCadastroPendente = null;
    try {
      wizSafra = null;
      wizAnimal = null;
      wizAqua = null;
      wizLoteQ = false;
      wizSwitch = null;
      wizTalhaoF = null;
      wizVinc = null;
      wizFunc = null;
      wizFuncRem = null;
      wizTarefa = null;
      wizTarCancel = null;
    } catch {}
  },
  get pendente() {
    return iaCadastroPendente;
  },
  get ready() {
    return iaReady;
  },
};
export { iaInit, iaChat, iaToolCall, iaVoz, entenderSistema, iaReset };
export const iaLocal = window.iaLocal;
export default window.iaLocal;

/* ===========================================================================
 * RACIOCINIO LOCAL (WebLLM) — extracao do bloco que ficava no fim da cadeia.
 *
 * Extraido para poder ser chamado ANTES do regex. A inversao e o ponto: sem
 * esta extracao, mover o bloco exigiria copiar ~50 linhas, e copia-e-cola e
 * como a cadeia voltaria a divergir em seis meses.
 *
 * As tools do modelo sao as 65 de /api/amplia/tools/ e cada chamada passa por
 * /api/amplia/exec/, que executa via sandbox.executar(via="mcp"). A antiga
 * iaToolCall — que fazia POST direto em /api/iot/comandos/ — fica desligada
 * por essa rota: uma IA que aciona valvula nao pode ter mao que nao passa por
 * confirmacao nem por auditoria.
 * ======================================================================== */
/* A conversa na nuvem, quando o switch manda. Vai pelo servidor
 * (`/api/ia/nuvem/`, que detém a chave) — nunca do browser direto, onde a
 * chave ficaria legível. Devolve o texto ou null (para cair no motor
 * local); nunca levanta, para não quebrar a cascata do `iaChat`. */
async function chatNuvem(msgs, onChunk) {
  try {
    if (typeof apiFetch !== 'function') return null;
    const lista = (Array.isArray(msgs) ? msgs : [])
      .filter((m) => m && (m.role === 'user' || m.role === 'assistant'))
      .slice(-8)
      .map((m) => ({ role: m.role, content: String(m.content || '').slice(0, 500) }));
    if (!lista.some((m) => m.role === 'user' && m.content.trim())) return null;
    const j = await apiFetch('/api/ia/nuvem/', {
      method: 'POST',
      body: JSON.stringify({ mensagens: lista }),
    });
    const texto = j && j.ok ? String(j.resposta || '').trim() : '';
    if (!texto) return null;
    if (typeof onChunk === 'function') {
      try {
        onChunk('', sanitizarResposta(texto));
      } catch {}
    }
    return sanitizarResposta(texto);
  } catch {
    return null;
  }
}

async function raciocinarLlm(opts) {
  const o = opts || {};
  const lastUser = o.lastUser;
  const msgs = o.msgs || [];
  const onChunk = o.onChunk;
  /* Switch "Usar agente da nuvem" LIGADO: a nuvem responde primeiro — é o
   * que o botão promete. Funciona até sem motor local (não exige iaEngine).
   * Falhou ou sem chave: cai no caminho local abaixo, sem avisar duas
   * vezes (o card da chave já diz quando falta chave). */
  try {
    if (
      window.IaModos &&
      typeof window.IaModos.activo === 'function' &&
      window.IaModos.activo('nuvem')
    ) {
      const nuvem = await chatNuvem(msgs, onChunk);
      if (nuvem) return nuvem;
    }
  } catch {}
  if (!iaEngine || iaReady === 'server' || !lastUser) return null;
  if (iaEngine && iaReady !== 'server') {
    const sysCtx = await entenderSistema();
    let systemContent =
      IA_SYSTEM + '\n\nCONTEXTO DO SISTEMA: ' + String(sysCtx || '').slice(0, 1200);
    /* As ferramentas entram AGORA, e vêm do servidor.
     *
     * Antes não entravam: a persona tinha uma lista escrita à mão, e as treze
     * eram fantasmas. Era aqui que a #27 fechava — o modelo nunca recebeu um
     * nome verdadeiro, e nenhuma chamada podia passar.
     *
     * `blocoFerramentas()` devolve o texto derivado ou, se o servidor não
     * responder, uma frase que diz que não há ferramentas. A terceira opção
     * — uma lista de recurso escrita à mão como plano B — seria
     * reintroduzir o defeito exactamente no sítio onde foi consertado.
     */
    const ferramentas = await blocoFerramentas();
    if (ferramentas) systemContent += '\n\n' + ferramentas;
    systemContent +=
      '\n\nREGRA ABSOLUTA: Nunca invente dados ou números. Se não souber um dado real, diga que não tem essa informação e sugira consultar no sistema. Nunca repita a mesma frase duas vezes. Respostas curtas e naturais em português.';
    /* Os modos de criação (`IaModos`, chaves da barra) entram no SYSTEM, e
     * nunca na mensagem do usuário. Na mensagem, o vocabulário da directiva
     * ("planilha", "gráfico", "widgets"...) sequestrava os matchers da
     * cascata determinística (`analisarIntent`, opções A/B/C, `^voltar`) —
     * que lêem o texto do produtor, não instruções. Aqui a cascata nem vê:
     * só o modelo. Capado curto: o contexto do motor local é pequeno e cada
     * token de instrução é um token a menos para os dados. */
    try {
      if (window.IaModos && typeof window.IaModos.directivas === 'function') {
        const dir = String(window.IaModos.directivas() || '').slice(0, 600);
        if (dir) systemContent += '\n\nMODO ATIVO: ' + dir;
      }
    } catch {}
    try {
      const props = await fetch('/api/propriedades/')
        .then((r) => (r.ok ? r.json() : null))
        .catch(() => null);
      if (props?.results?.[0]) {
        systemContent += `\nDADOS LOCAIS: propriedade=${props.results[0].nome}`;
        try {
          window._iaPropPadrao = props.results[0].id;
        } catch {}
      }
    } catch {}
    /* Histórico podado: últimas 6 msgs, 500 chars cada (cabe nos 4096 tokens) */
    const histCorto = (msgs || [])
      .filter((m) => m.role !== 'system')
      .slice(-6)
      .map((m) => ({ role: m.role, content: String(m.content || '').slice(0, 500) }));
    async function chamarLLM(ms) {
      const chunks = await iaEngine.chat.completions.create({
        messages: [{ role: 'system', content: systemContent }, ...ms],
        temperature: 0.3,
        max_tokens: 256,
        stream: true,
      });
      let out = '';
      for await (const c of chunks) {
        const delta = c.choices[0]?.delta?.content || '';
        out += delta;
        if (onChunk) onChunk(delta, sanitizarResposta(out));
      }
      return sanitizarResposta(out);
    }
    try {
      try {
        var out = await chamarLLM(histCorto);
      } catch (e1) {
        /* Contexto estourou: tenta de novo com histórico mínimo */
        if (/context|Context|tokens/i.test(String((e1 && e1.message) || e1))) {
          console.warn('[IA] contexto cheio, retentando enxuto');
          out = await chamarLLM(histCorto.slice(-2));
        } else throw e1;
      }
      // Se o LLM retornou uma tool call, executa e humaniza
      if (out.includes('"tool"')) {
        const toolRes = await toolCallGovernada(out);
        if (toolRes) return sanitizarResposta(toolRes);
      }
      return out;
    } catch (e) {
      console.warn('[IA] LLM falhou:', e && e.message ? e.message : e);
    }
  }

  return sanitizarResposta(out);
}

/* toolCallGovernada — a unica mao do modelo local.
 *
 * SUBSTITUI a antiga `iaToolCall`, que era o problema de seguranca que o BUILD 0
 * existiu para fechar. O que ela fazia:
 *
 *     if (tool === 'irrigacao') {
 *       await apiFetch('/api/iot/comandos/', { method: 'POST', ... });
 *     }
 *
 * POST direto na API de comandos. Uma IA de 1.7B num celular podia acionar uma
 * VALVULA de irrigacao sem passar por `sandbox.executar`, sem `needs_confirm`,
 * sem uma linha em `IAExecucao` e sem checagem de flag. E o parsing da chamada
 * era `text.match(/\\{[^]*"tool"[^]*\\}/)`, que casa o primeiro `{` com o ultimo
 * `}` da resposta — com qualquer raciocinio que mencione JSON no meio, a
 * expressao pegava o bloco errado.
 *
 * Agora:
 *   1. o modelo recebe o catalogo de /api/amplia/tools/ (as 65 intents);
 *   2. a chamada sai por /api/amplia/exec/, que executa via sandbox.executar;
 *   3. o servidor decide se e leitura (responde) ou escrita (pede confirmacao).
 *
 * O RESULTADO E' IDENTICO para quem pergunta, e governado para quem age.
 */

/** Cache do catalogo de tools: o painel nao deve buscar 65 schemas a cada msg. */
let _toolsAmplia = null;
let _toolsEm = 0;
const TTL_TOOLS = 10 * 60 * 1000;

async function catalogoToolsAmplia() {
  const agora = Date.now();
  if (_toolsAmplia && agora - _toolsEm < TTL_TOOLS) return _toolsAmplia;
  try {
    const r = await apiFetch('/api/amplia/tools/');
    _toolsAmplia = (r && r.tools) || [];
    _toolsEm = agora;
  } catch (e) {
    console.warn('[IA] catalogo de tools indisponivel:', e && e.message);
    _toolsAmplia = null;
  }
  return _toolsAmplia || [];
}

/**
 * Extrai a tool call da saida do modelo.
 *
 * Deliberadamente NAO usa a regex gulenta antiga. Aqui procuramos o primeiro
 * objeto JSON balanceado que tenha "tool" como chave, percorrendo os
 *candidatos e respeitando strings e escapes. Um modelo pequeno produz
 * ```
 * {"tool": "amplia_clima_agora", "args": {}}
 * ```
 * e nao uma resposta limpa; a extracao precisa sobreviver ao texto em volta
 * sem pegar o objeto errado.
 */
function extrairToolCall(texto) {
  const s = String(texto || '');
  for (let i = 0; i < s.length; i++) {
    if (s[i] !== '{') continue;
    // `lerObjetoJson` devolve `{ valor, fim }` — o objeto parseado está em
    // `valor`. Ler `obj.tool` dá sempre `undefined`, e o resultado é que a
    // EXTRAÇÃO NUNCA ACERTA: toda a tool call do modelo local morria aqui,
    // com `null`, sem mensagem e sem nenhuma pista do porque.
    //
    // Este não era um bug de nomes (FILA #27) — era um bug uma camada mais
    // abaixo, e era invisível enquanto a lista do prompt fosse de nomes
    // errados: os dois defeitos davam o mesmo sintoma do lado de fora
    // (`tool_fora_do_catalogo`) e escondiam um atrás do outro. Corrigir os
    // nomes sem corrigir isto daria a impressão de ter resolvido, e o
    // produtor continuaria sem ver a IA fazer nada.
    //
    // O mesmo desvio já foi corrigido em `proativo-local.js`, com um
    // comentário a avisar. Duas cópias da mesma função, uma certa e outra
    // não — e a que não estava certa é a do chat.
    const lido = lerObjetoJson(s, i);
    if (!lido) continue;
    const obj = lido.valor;
    if (obj && typeof obj.tool === 'string' && obj.tool) {
      return { tool: obj.tool, args: obj.args || obj.arguments || {} };
    }
  }
  return null;
}

/**
 * Le um objeto JSON a partir de `ini`.
 *
 * Devolve `{ valor, fim }` — `valor` é o objeto JÁ PARSEADO e `fim` o índice
 * a seguir ao `}` que o fechou. Devolve `null` se o que está a partir de
 * `ini` não for JSON válido, para o chamador tentar a próxima `{`.
 *
 * Esta docstring dizia "devolvendo o texto", e a leitura em
 * `extrairToolCall` tratava o retorno como se fosse o objeto. Duas coisas
 * erradas que se cancelavam: `obj.tool` é `undefined`, o `if` nunca entrava
 * e a extracção devolvia `null` sempre — o mesmo sintoma de "o modelo não
 * pediu nada" quando o modelo tinha pedido.
 */
function lerObjetoJson(s, ini) {
  let profundidade = 0;
  let emString = false;
  let escape = false;
  for (let i = ini; i < s.length; i++) {
    const c = s[i];
    if (escape) {
      escape = false;
      continue;
    }
    if (c === '\\') {
      if (emString) escape = true;
      continue;
    }
    if (c === '"') {
      emString = !emString;
      continue;
    }
    if (emString) continue;
    if (c === '{') profundidade++;
    else if (c === '}') {
      profundidade--;
      if (profundidade === 0) {
        const bruto = s.slice(ini, i + 1);
        try {
          return { valor: JSON.parse(bruto), fim: i + 1 };
        } catch (e) {
          return null; // nao e JSON valido; tenta a proxima '{'
        }
      }
    }
  }
  return null;
}

/**
 * Executa UMA tool pelo caminho governado.
 * Devolve null quando a saida do modelo nao era tool call — nesse caso quem
 * responde e o proprio texto do modelo.
 */
async function toolCallGovernada(texto, entradaUsuario) {
  const call = extrairToolCall(texto);
  if (!call) return null;

  // O prefixo e do servidor. Um modelo pequeno pode omitir, e o erro aqui
  // seria "tool desconhecida" — confuso para quem perguntas. Normaliza.
  let nome = call.tool;
  if (nome && !nome.startsWith('amplia_')) nome = 'amplia_' + nome;

  try {
    const r = await apiFetch('/api/amplia/exec/', {
      method: 'POST',
      body: JSON.stringify({ tool: nome, args: call.args, entrada: entradaUsuario || '' }),
    });
    if (!r) return `Nao consegui executar ${call.tool}.`;

    // o sandbox sinaliza pedido de confirmacao no proprio texto da resposta;
    // ele ja vem pronto para o produtor, entao nao reescrevemos nada
    // `r.ok` é obrigatório antes de dizer "executada".
    //
    // `/api/amplia/exec/` responde **HTTP 200** mesmo quando a tool falha, por
    // decisão deliberada da view: um erro de tool é um RESULTADO, não erro de
    // HTTP, porque um 4xx faria o cliente repetir e executar a acção duas
    // vezes. A consequência: `ok:false` chega aqui como resposta normal, e o
    // `textoResposta` abaixo — que só olhava `resposta`/`erro` — caía no
    // fallback e dizia:
    //
    //     "Ferramenta amplia_x executada."
    //
    // para uma acção que o servidor RECUSOU. O produtor lia que a água ligou.
    // Não ligou.
    if (r.ok === false) {
      const motivo = r.erro || r.motivo || `recusada pelo servidor (${r.codigo || 'sem codigo'})`;
      console.warn('[IA] tool recusada', nome, r.codigo || '', motivo);
      return sanitizarResposta(motivo) || `A acao ${call.tool} nao foi executada.`;
    }
    const textoResposta = r.resposta || r.erro || '';
    if (r.executucao_id) {
      console.log('[IA] tool governada', nome, 'exec', r.executucao_id, 'ok=', r.ok);
    }
    return sanitizarResposta(textoResposta) || `Ferramenta ${call.tool} executada.`;
  } catch (e) {
    console.warn('[IA] tool governada falhou:', e && e.message);
    return `Erro ao executar ${call.tool}: ${e && e.message ? e.message : 'falha'}.`;
  }
}

/* ===========================================================================
 * PONTE DE INTEGRACAO — o que o pipeline de AUDIO consome
 * ===========================================================================
 * Estas funcoes NAO sao novas: sao as mesmas que atendem o chat, expostas.
 * O ponto do design e que o audio nao tem caminho proprio de raciocinio nem
 * de execucao. Se ele tivesse, teriamos dois lugares onde uma acao pode
 * acontecer, e o lugar novo nao herdaria a confirmacao nem a auditoria.
 */

/** O motor local, para quem quiser saber se ha WebGPU de verdade. */
export function obterIaEngine() {
  return iaEngine && iaReady !== 'server' ? iaEngine : null;
}

/**
 * Roda um prompt no mesmo motor do chat.
 *
 * Diferente de `raciocinarLlm`, que monta o system prompt com o contexto do
 * sistema e o historico do chat, aqui o prompt JA E completo: quem chama sabe
 * exatamente o que o modelo tem de ver. Misturar os dois tipos de chamada
 * seria a forma mais curta de o modelo receber instrucoes conflitantes.
 */
export async function raciocinarComPrompt(prompt, opts = {}) {
  if (!iaEngine || iaReady === 'server') return null;
  const r = await iaEngine.chat.completions.create({
    messages: [
      { role: 'system', content: IA_SYSTEM },
      { role: 'user', content: String(prompt || '').slice(0, 6000) },
    ],
    temperature: opts.temperature != null ? opts.temperature : 0.2,
    max_tokens: opts.maxTokens || 200,
    stream: false,
  });
  const txt =
    r && r.choices && r.choices[0] && r.choices[0].message ? r.choices[0].message.content : '';
  return txt || '';
}

/**
 * Sinais da primeira versão de uma transcricao, vindos do SERVIDOR.
 *
 * O backend tem a mesma logica em `app/ia/ingestao/audio.py` (talhao,
 * quantidade, classe de insumo). Reimplementar em JS criaria duas respostas
 * para a mesma frase — e o produtor veria "talhao 4" na tela e "talhao 3" no
 * log. Se o servidor estiver fora, devolvemos vazio: o LLM aindaraciocina
 * sobre a transcricao inteira, so perde as pistas.
 */
export async function extrairSinaisAudio(texto) {
  if (!texto) return null;
  try {
    const r = await apiFetch('/api/amplia/ingestao/audio/sinais/', {
      method: 'POST',
      body: JSON.stringify({ texto: String(texto).slice(0, 2000) }),
    });
    return (r && r.sinais) || null;
  } catch (e) {
    console.warn('[IA] sinais de audio indisponiveis:', e && e.message);
    return null;
  }
}

export { catalogoToolsAmplia, toolCallGovernada, extrairToolCall, lerObjetoJson };

/* A UI chama isto pelo nome. Um global nomeado e feio; um global sem nome
 * nenhum e pior: nao ha como descobrir que existe. */
if (typeof window !== 'undefined') {
  window.__ampliaToolGovernada = toolCallGovernada;
  window.__ampliaIa = {
    engine: obterIaEngine,
    raciocinar: raciocinarComPrompt,
    sinais: extrairSinaisAudio,
    catalogo: catalogoToolsAmplia,
  };
}
