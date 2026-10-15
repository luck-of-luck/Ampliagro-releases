'use strict';

// ============================================
// FUNÇÃO PARA GERAR MATRIZ DO CALENDÁRIO - COM DADOS VAZIOS
// ============================================
function gerarMatrizCalendarioAgenda() {
  // Retorna matriz vazia - sem dados simulados
  return [];
}

// ============================================
// FUNÇÃO PARA ABRIR MODAL TAREFAS
// ============================================
function abrirModalTarefa() {
  const backdrop = document.getElementById('modalNovaTarefaBackdrop');
  if (backdrop) {
    backdrop.classList.remove('hidden');
    backdrop.classList.add('flex');
  }
}

// ============================================
// FUNÇÃO PARA FECHAR MODAL TAREFAS
// ============================================
function fecharModalTarefa() {
  const backdrop = document.getElementById('modalNovaTarefaBackdrop');
  if (backdrop) {
    backdrop.classList.add('hidden');
    backdrop.classList.remove('flex');
  }
}

// ============================================
// FUNÇÃO PARA FILTRAR POR CARGO NA AGENDA
// ============================================
function filtrarAgendaPorCargo() {
  const cargosSelecionados = [];
  const checkboxes = document.querySelectorAll('input[name="profissao_filtro"]:checked');
  checkboxes.forEach((cb) => {
    cargosSelecionados.push(parseInt(cb.value));
  });
  console.log('Filtrando agenda por cargos:', cargosSelecionados);
}

// ============================================
// AGENDA PRINCIPAL - RENDER COM SHADCN UI / BENTO GRID CONCEPT
// ============================================
function renderAgendaTab(data) {
  const funcionarios_reais = data && data.funcionarios_reais ? data.funcionarios_reais : [];
  const tarefas = data && data.tarefas ? data.tarefas : [];
  const mes_atual = data && data.mes_atual ? data.mes_atual : 6;
  const ano_atual = data && data.ano_atual ? data.ano_atual : 2026;
  const mes_nome_str = data && data.mes_nome_str ? data.mes_nome_str : '';
  const prev_mes = data && data.prev_mes ? data.prev_mes : 5;
  const prev_ano = data && data.prev_ano ? data.prev_ano : 2026;
  const next_mes = data && data.next_mes ? data.next_mes : 7;
  const next_ano = data && data.next_ano ? data.next_ano : 2026;
  const cargos = data && data.cargos ? data.cargos : [];
  const cargos_ativos_ids = data && data.cargos_ativos_ids ? data.cargos_ativos_ids : [];
  const data_selecionada_str = data && data.data_selecionada_str ? data.data_selecionada_str : '';

  let html = `<div class="px-6 py-5 space-y-5 bg-ncs-50 dark:bg-ncs-900 min-h-screen text-ncs-900 dark:text-ncs-50">
        
        <!-- Hero Header - Bento Card -->
        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
            <div class="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
                <div>
                    <div class="flex items-center gap-3 mb-2">
                        <span class="px-3 py-1.5 text-xs font-medium rounded-md bg-emerald-100 dark:bg-emerald-900/50 text-emerald-800 dark:text-emerald-200"><i class="bi bi-calendar2-week-fill"></i> Operação planejada</span>
                        <span class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium">Escala, ordens e rotina de campo</span>
                    </div>
                    <h3 class="text-xl font-bold text-ncs-900 dark:text-ncs-50 mb-1">Escala de Tarefas e Rotinas de Campo</h3>
                    <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium"><i class="bi bi-geo-alt-fill text-emerald-600 dark:text-emerald-500"></i> Coordenação visual das atividades operacionais</small>
                </div>
                <button type="button" id="btnNovaTarefa" 
                        class="px-4 py-2 font-medium text-white bg-emerald-600 dark:bg-emerald-700 border border-emerald-600 dark:border-emerald-700 rounded-md hover:bg-emerald-700 dark:hover:bg-emerald-600 transition-all duration-150 flex items-center gap-2">
                    <i class="bi bi-plus-circle-fill"></i> Nova Ordem de Serviço
                </button>
            </div>
        </div>

        <!-- Grid Principal: Calendário + Checklist -->
        <div class="grid grid-cols-1 xl:grid-cols-5 gap-5">
            
            <!-- Coluna do Calendário - 2/5 largura -->
            <div class="xl:col-span-2 space-y-4">
                
                <!-- Calendário com dados do mês atual -->
                <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
                    <div class="flex items-center justify-between mb-4">
                        <a href="?mes=${prev_mes}&ano=${prev_ano}" 
                           class="px-2 py-1 text-xs font-medium rounded-md border border-ncs-900/30 dark:border-ncs-50/30 bg-ncs-50 dark:bg-ncs-900 text-ncs-900 dark:text-ncs-50 hover:bg-ncs-50/80 dark:hover-bg-ncs-900/80 transition-all duration-150">
                            <i class="bi bi-chevron-left"></i>
                        </a>
                        <span class="text-sm font-semibold text-ncs-900 dark:text-ncs-50">${mes_nome_str || 'Mês'} de ${ano_atual}</span>
                        <a href="?mes=${next_mes}&ano=${next_ano}" 
                           class="px-2 py-1 text-xs font-medium rounded-md border border-ncs-900/30 dark:border-ncs-50/30 bg-ncs-50 dark:bg-ncs-900 text-ncs-900 dark:text-ncs-50 hover:bg-ncs-50/80 dark:hover-bg-ncs-900/80 transition-all duration-150">
                            <i class="bi bi-chevron-right"></i>
                        </a>
                    </div>
                    
                    <div class="grid grid-cols-7 gap-1.5">
        `;

  // Cabeçalho dos dias da semana
  const diasSemana = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];
  diasSemana.forEach((dia) => {
    html += `                        <div class="text-center text-xs font-semibold text-ncs-900/50 dark:text-ncs-900/50 py-2">${dia}</div>
        `;
  });

  // Renderizar calendário vazio
  const matrizCalendario = gerarMatrizCalendarioAgenda();
  if (matrizCalendario.length === 0) {
    // Calendário vazio - sem dados simulados
    for (let i = 0; i < 7; i++) {
      for (let j = 0; j < 7; j++) {
        html += `                        <div class="h-14"></div>
        `;
      }
    }
  } else {
    matrizCalendario.forEach((semana) => {
      semana.forEach((slot) => {
        if (slot.dia) {
          let dayClasses =
            'bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 text-ncs-900 dark:text-ncs-50 rounded-md transition-all h-14 p-1 flex flex-col items-center justify-center cursor-pointer hover:bg-ncs-50 dark:hover:bg-ncs-900';
          let badgeHtml = '';

          if (slot.is_hoje) {
            dayClasses =
              'border-2 border-emerald-500 text-emerald-600 dark:text-emerald-500 font-bold bg-emerald-50 dark:bg-emerald-900/20 rounded-md transition-all h-14 p-1 flex flex-col items-center justify-center cursor-pointer';
          }

          if (slot.total_tarefas > 0) {
            badgeHtml = `<span class="px-1 py-0.5 text-[10px] font-medium rounded bg-emerald-600 text-white mt-0.5">${slot.total_tarefas} O.S</span>`;
          }

          html += `                        <div class="${dayClasses}">
                            <span class="text-sm font-medium">${slot.dia}</span>
                            ${badgeHtml}
                        </div>
        `;
        } else {
          html += `                        <div class="h-14"></div>
        `;
        }
      });
    });
  }

  html += `                    </div>
                </div>
                
                <!-- Filtro por Cargos -->
                <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
                    <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider block mb-3">Filtrar por Especialidade Operacional</span>
                    <div class="grid grid-cols-1 gap-2 max-h-48 overflow-y-auto pr-1">
        `;

  // Cargos para filtro - lista vazia
  if (cargos.length > 0) {
    cargos.forEach((c) => {
      const checked = cargos_ativos_ids.includes(c.id) ? 'checked' : '';
      html += `                        <label class="flex items-center py-1.5 px-2 rounded hover:bg-ncs-50 dark:hover:bg-ncs-900 cursor-pointer transition-all duration-150">
                            <input class="w-4 h-4 mr-2.5 text-emerald-600 dark:text-emerald-500 bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded focus:ring-emerald-500" 
                                   type="checkbox" name="profissao_filtro" value="${c.id}" id="f-${c.id}" ${checked} onchange="filtrarAgendaPorCargo()">
                            <span class="text-xs text-ncs-900 dark:text-ncs-50 truncate">${c.nome}</span>
                        </label>
        `;
    });
  }

  html += `                    </div>
                </div>
                
            </div>
            
            <!-- Coluna do Checklist - 3/5 largura -->
            <div class="xl:col-span-3">
                <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none h-full flex flex-col transition-all duration-200">
                    <div class="flex items-center justify-between mb-4 border-b border-ncs-900/20 dark:border-ncs-50/20/80 pb-3">
                        <h5 class="text-ncs-900 dark:text-ncs-50 font-bold m-0 text-sm uppercase tracking-wider">Checklist de Atividades Solicitadas</h5>
        `;

  if (data_selecionada_str) {
    html += `                        <span class="px-2 py-1 text-xs font-bold rounded-md bg-emerald-600 dark:bg-emerald-700 text-white">${data_selecionada_str}</span>
        `;
  } else {
    html += `                        <span class="px-2 py-1 text-xs font-medium border border-ncs-900/30 dark:border-ncs-50/30 bg-ncs-50/80 dark:bg-ncs-900/80 text-ncs-900/70 dark:text-ncs-50/70 rounded-md">Todas as Ordens do Mês</span>
        `;
  }

  html += `                    </div>
                    
                    <div class="flex-1 overflow-y-auto pr-1 -mr-1" style="max-height: 520px;">
        `;

  // Tarefas - Checklist dinâmico (lista vazia)
  if (tarefas.length > 0) {
    tarefas.forEach((t) => {
      let statusClass =
        'border border-ncs-900/30 dark:border-ncs-50/30 text-ncs-900 dark:text-ncs-50';
      let statusText = t.status_display || t.get_status_display || t.status || 'Status';
      let statusColor = '#64748b';

      if (t.status === 'PENDENTE' || t.status === 'pendente') {
        statusClass =
          'border border-red-300 dark:border-red-700 text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20';
        statusColor = '#dc3545';
      } else if (t.status === 'EXECUCAO' || t.status === 'execucao') {
        statusClass =
          'border border-amber-300 dark:border-amber-700 text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20';
        statusColor = '#ffc107';
      } else if (t.status === 'CONCLUIDO' || t.status === 'concluido') {
        statusClass = 'bg-emerald-600 dark:bg-emerald-700 text-white';
        statusColor = '#28a745';
      }

      // Processar responsáveis
      let responsaveisHtml = '';
      if (t.responsaveis && t.responsaveis.length > 0) {
        t.responsaveis.forEach((r) => {
          responsaveisHtml += `<span class="px-2 py-0.5 mr-1 mb-1 text-xs font-medium rounded-md bg-ncs-50/80 dark:bg-ncs-900/80 text-ncs-900 dark:text-ncs-50 inline-block">${r.nome}</span>`;
        });
      } else {
        responsaveisHtml =
          '<span class="text-xs text-ncs-900/50 dark:text-ncs-900/50">Manejo Geral</span>';
      }

      html += `                        <div class="border-b border-ncs-900/20 dark:border-ncs-50/20/80 last:border-0 py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                            <div class="flex items-start sm:items-center gap-3">
                                <span class="w-3 h-3 flex-shrink-0 rounded-full mt-1 sm:mt-0" style="background-color: ${statusColor};"></span>
                                <div>
                                    <h6 class="font-semibold text-ncs-900 dark:text-ncs-50 text-sm mb-1">${t.nome || 'Tarefa não identificada'}</h6>
                                    <div class="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-3">
                                        <small class="text-ncs-900/50 dark:text-ncs-900/50 text-xs"><i class="bi bi-clock"></i> Manejo Limite: <strong class="text-red-600 dark:text-red-400">${t.prazo || 'N/D'}</strong></small>
                                        <small class="text-ncs-900/50 dark:text-ncs-900/50 text-xs">Operadores: ${responsaveisHtml}</small>
                                    </div>
                                </div>
                            </div>
                            <form method="post" action="." class="flex-shrink-0">
                                <input type="hidden" name="acao" value="mudar_status">
                                <input type="hidden" name="tarefa_id" value="${t.id || ''}">
                                <button type="submit" class="px-3 py-1.5 text-xs font-semibold rounded-md border transition ${statusClass}">
                                    ${statusText}
                                </button>
                            </form>
                        </div>
        `;
    });
  } else {
    html += `                        <div class="flex flex-col items-center justify-center py-12 text-ncs-900/50 dark:text-ncs-900/50">
                            <i class="bi bi-calendar-check text-5xl opacity-20 mb-3"></i>
                            <span class="text-xs font-semibold block">Nenhuma ordem de serviço localizada para os parâmetros atuais.</span>
                        </div>
        `;
  }

  html += `                    </div>
                </div>
            </div>
            
        </div>
    </div>

    <!-- Modal Nova Tarefa - 100% Adaptativo Shadcn UI -->
    <div class="fixed inset-0 bg-black/50 dark:bg-black/70 z-50 items-center justify-center hidden transition-all duration-200" id="modalNovaTarefaBackdrop">
        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md shadow-xl w-full max-w-xl mx-4 max-h-[90vh] overflow-y-auto transition-colors duration-200">
            <div class="flex items-center justify-between px-5 py-4 border-b border-ncs-900/20 dark:border-ncs-50/20/80 bg-emerald-600 dark:bg-emerald-700 rounded-t-md">
                <h5 class="text-lg font-bold text-white m-0 flex items-center gap-2"><i class="bi bi-plus-circle"></i> Nova Ordem de Serviço</h5>
                <button type="button" onclick="fecharModalTarefa()" class="text-white text-xl font-medium hover:opacity-80 transition-opacity">&times;</button>
            </div>
            <form method="post" action=".">
                <input type="hidden" name="acao" value="adicionar">
                <div class="p-5 bg-ncs-50 dark:bg-ncs-900">
                    
                    <div class="mb-4">
                        <label class="text-xs font-semibold text-ncs-900 dark:text-ncs-50 mb-1.5 block">Operação / Atividade:</label>
                        <input type="text" name="nome_tarefa" required
                               class="w-full px-3 py-2 bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded-md text-ncs-900 dark:text-ncs-50 focus:ring-1 focus:ring-emerald-500 focus:outline-none transition-all duration-150 placeholder:text-ncs-900/50" 
                               placeholder="Ex: Pulverização Setor Sul">
                    </div>
                    
                    <div class="mb-4">
                        <label class="text-xs font-semibold text-ncs-900 dark:text-ncs-50 mb-1.5 block">Data Limite de Campo:</label>
                        <input type="date" name="prazo" required
                               class="w-full px-3 py-2 bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded-md text-ncs-900 dark:text-ncs-50 focus:ring-1 focus:ring-emerald-500 focus:outline-none transition-all duration-150">
                    </div>
                    
                    <div class="mb-4">
                        <label class="text-xs font-semibold text-ncs-900 dark:text-ncs-50 mb-1.5 block">Responsáveis pelo Manejo:</label>
                        <select name="responsavel" multiple required
                                class="w-full px-3 py-2 bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded-md text-ncs-900 dark:text-ncs-50 focus:ring-1 focus:ring-emerald-500 focus:outline-none transition-all duration-150" style="min-height: 110px;">
        `;

  // Funcionários no select do modal - lista vazia
  funcionarios_reais.forEach((f) => {
    html += `                            <option value="${f.id}">${f.nome} (${f.cargo_nome || 'Operário'})</option>
        `;
  });

  html += `                        </select>
                    </div>
                    
                </div>
                <div class="flex items-center justify-end gap-2 px-5 py-3 border-t border-ncs-900/20 dark:border-ncs-50/20/80 bg-ncs-50/80 dark:bg-ncs-900 rounded-b-md">
                    <button type="button" onclick="fecharModalTarefa()" 
                            class="px-4 py-2 font-medium text-ncs-900 dark:text-ncs-50 bg-white dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded-md hover:bg-ncs-50 dark:hover:bg-ncs-900 transition-all duration-150">
                        Fechar
                    </button>
                    <button type="submit" 
                            class="px-4 py-2 font-medium text-white bg-emerald-600 dark:bg-emerald-700 border border-emerald-600 dark:border-emerald-700 rounded-md hover:bg-emerald-700 dark:hover:bg-emerald-600 transition-all duration-150">
                        Gravar Atividade
                    </button>
                </div>
            </form>
        </div>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const btnNovaTarefa = document.getElementById('btnNovaTarefa');
            if (btnNovaTarefa) {
                btnNovaTarefa.addEventListener('click', abrirModalTarefa);
            }
        });
    </script>
    `;

  return html;
}

// ============================================
// AGENDA DE ANÁLISES - Rota: /api/agenda-analises/
// ============================================
function renderAgendaAnalisesTab(data) {
  const talhoes_mapa = data && data.talhoes_mapa ? data.talhoes_mapa : [];
  const laudos = data && data.laudos ? data.laudos : [];
  const labels_grafico = data && data.labels_grafico ? data.labels_grafico : [];
  const valores_calcario = data && data.valores_calcario ? data.valores_calcario : [];

  let html = `<div class="px-6 py-5 space-y-5 bg-ncs-50 dark:bg-ncs-900 min-h-screen text-ncs-900 dark:text-ncs-50">
        
        <div class="flex items-center justify-between mb-4 pb-3 border-b border-ncs-900/20 dark:border-ncs-50/20/80">
            <div>
                <h3 class="text-xl font-bold text-ncs-900 dark:text-ncs-50 mb-0">Auditoria Química e Diagnóstico de Solo</h3>
                <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium"><i class="bi bi-shield-check text-emerald-600 dark:text-emerald-500"></i> Monitoramento de Amostragens de Laboratório</small>
            </div>
            <div class="flex items-center gap-2">
    `;

  html += `                <a href="?export=xlsx_analise" 
                   class="flex items-center justify-center gap-2 px-3 py-2 font-medium text-xs rounded-md bg-emerald-600 dark:bg-emerald-700 border border-emerald-600 dark:border-emerald-700 text-white hover:bg-emerald-700 dark:hover:bg-emerald-600 transition-all duration-150">
                    <i class="bi bi-download"></i> Baixar Planilha Modelo
                </a>
            </div>
        </div>

        <!-- Painel para nova área -->
        <div class="mb-4" id="painelMapeamentoTalhao">
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-colors duration-200">
                <h5 class="text-emerald-600 dark:text-emerald-500 font-bold mb-3"><i class="bi bi-brush"></i> Configurar Demarcação de Área Terrestre</h5>
                <form method="post" action=".">
                    <input type="hidden" name="acao" value="gravar_talhao">
    `;

  html += `                    <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
                        <div>
                            <label class="text-xs font-semibold text-ncs-900 dark:text-ncs-50 mb-1.5 block">Identificador do Talhão:</label>
                            <input type="text" name="nome_talhao" required
                                   class="w-full px-3 py-2 bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded-md text-ncs-900 dark:text-ncs-50 focus:ring-1 focus:ring-emerald-500 focus:outline-none transition-all duration-150 placeholder:text-ncs-900/50" 
                                   placeholder="Ex: Talhão Sul - Soja">
                        </div>
                        <div>
                            <label class="text-xs font-semibold text-ncs-900 dark:text-ncs-50 mb-1.5 block">Diagnóstico Químico (pH Estimado):</label>
                            <select name="status_ph" required
                                    class="w-full px-3 py-2 bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded-md text-ncs-900 dark:text-ncs-50 focus:ring-1 focus:ring-emerald-500 focus:outline-none transition-all duration-150">
                                <option value="4.5">Crítico - Necessita Calagem Urgente (pH 4.5)</option>
                                <option value="5.4">Moderado - Acidez de Campo (pH 5.4)</option>
                                <option value="6.5">Corrigido - Solo Equilibrado (pH 6.5)</option>
                            </select>
                        </div>
    `;

  html += `                        <div class="md:col-span-2">
                            <label class="text-xs font-semibold text-ncs-900 dark:text-ncs-50 mb-1.5 block">Polígono Geográfico (Coordenadas JSON):</label>
                            <input type="text" name="coordenadas_json" value="[]" required
                                   class="w-full px-3 py-2 bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded-md text-ncs-900 dark:text-ncs-50 focus:ring-1 focus:ring-emerald-500 focus:outline-none transition-all duration-150">
                        </div>
                        <div class="md:col-span-4 text-right pt-2">
                            <button type="submit" 
                                    class="px-5 py-2 font-medium text-white bg-emerald-600 dark:bg-emerald-700 border border-emerald-600 dark:border-emerald-700 rounded-md hover:bg-emerald-700 dark:hover:bg-emerald-600 transition-all duration-150">
                                Salvar Área
                            </button>
                        </div>
                    </div>
                </form>
            </div>
        </div>
    `;

  html += `
        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-colors duration-200">
            <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider block mb-3"><i class="bi bi-journal-medical"></i> Prescrições e Diretrizes Agronómicas de Correção</span>
            <div class="overflow-x-auto">
                <table class="w-full text-sm">
                    <thead class="bg-ncs-50/80 dark:bg-ncs-900/50">
                        <tr class="text-ncs-900/70 dark:text-ncs-50/70 text-xs uppercase tracking-wider">
                            <th class="text-left py-3 px-4 font-medium">Talhão Correlato</th>
                            <th class="py-3 px-4 font-medium">Acidez Analisada (pH)</th>
                            <th class="text-left py-3 px-4 font-medium">Diretrizes de Manejo Clínico de Campo</th>
                            <th class="py-3 px-4 font-medium">Status Operacional</th>
                            <th class="py-3 px-4 font-medium">Ações</th>
                        </tr>
                    </thead>
                    <tbody class="text-ncs-900 dark:text-ncs-50 divide-y divide-ncs-900/20 dark:divide-ncs-50/20/80">
    `;

  // Laudos - lista vazia
  if (laudos.length > 0) {
    laudos.forEach((laudo) => {
      html += `                        <tr>
                            <td class="font-bold text-ncs-900 dark:text-ncs-50 py-3 px-4 text-left"><strong>${laudo.talhao || 'Safra não identificada'}</strong></td>
                            <td class="py-3 px-4 text-center"><span class="px-2 py-0.5 text-xs font-bold rounded-md bg-ncs-50/80 dark:bg-ncs-900/80 text-ncs-900 dark:text-ncs-50">pH ${parseFloat(laudo.ph_solo || 0).toFixed(1)}</span></td>
                            <td class="text-left text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium py-3 px-4 max-w-[450px]" style="white-space: normal;">${laudo.recomendacao || 'Sem recomendação'}</td>
                            <td class="py-3 px-4 text-center"><span class="px-2 py-0.5 font-bold rounded-md bg-emerald-100 dark:bg-emerald-800/50 text-emerald-800 dark:text-emerald-200 text-xs">Homologado</span></td>
                            <td class="py-3 px-4 text-center">
                                <form method="post" action="." onsubmit="return confirm('Deseja realmente remover esta diretriz analítica?');" class="inline">
                                    <input type="hidden" name="acao" value="excluir_laudo">
                                    <input type="hidden" name="id_laudo" value="${laudo.id}">
                                    <button type="submit" class="px-2.5 py-1 text-xs font-bold rounded-md border border-red-300 dark:border-red-700 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 transition-all duration-150">Excluir</button>
                                </form>
                            </td>
                        </tr>
    `;
    });
  } else {
    html += `                        <tr>
                            <td colspan="5" class="py-4 text-center text-ncs-900/50 dark:text-ncs-900/50 font-bold">Nenhum laudo químico ou amostragem processada para este filtro. Utilize a toolbar acima.</td>
                        </tr>
    `;
  }

  html += `                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        document.addEventListener("DOMContentLoaded", function() {
            var ctx = document.getElementById("chartNutrientesCarentes");
            if (ctx && window.Chart) {
                var palAcc = getComputedStyle(document.documentElement).getPropertyValue("--pal-accent").trim() || "#0f9d6e";
                var palFill = getComputedStyle(document.documentElement).getPropertyValue("--pal-accent-fill").trim() || "rgba(83, 221, 108, 0.3)";
                new Chart(ctx, {
                    type: "bar",
                    data: {
                        labels: [],
                        datasets: [{
                            label: "Necessidade Calcario (Ton/Ha)",
                            data: [],
                            backgroundColor: palFill,
                            borderColor: palAcc,
                            borderWidth: 1,
                            borderRadius: 4
                        }]
                    },
                    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
                });
            }
        });
    </script>
    `;

  return html;
}

// ============================================
// AGENDA DE PRODUÇÃO - Rota: /api/agenda-producao/
// ============================================
function renderAgendaProducaoTab(data) {
  const safras = data && data.safras ? data.safras : [];
  const janelas_inteligentes = data && data.janelas_inteligentes ? data.janelas_inteligentes : [];
  const area_total = data && data.area_total !== undefined ? data.area_total : 0.0;

  let html = `<div class="px-6 py-5 space-y-5 bg-ncs-50 dark:bg-ncs-900 min-h-screen text-ncs-900 dark:text-ncs-50">
        
        <div class="flex items-center justify-between mb-4 pb-3 border-b border-ncs-900/20 dark:border-ncs-50/20/80">
            <div>
                <h3 class="text-xl font-bold text-ncs-900 dark:text-ncs-50 mb-0">Planejamento Agrícola e Agenda de Produção</h3>
                <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium"><i class="bi bi-calendar-check text-emerald-600 dark:text-emerald-500"></i> Cronograma de Plantio, Manejo de Safras e Estimativas de Colheita</small>
            </div>
    `;

  html += `        </div>

        <!-- Painel para nova safra -->
        <div class="mb-4">
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-colors duration-200">
                <h5 class="text-emerald-600 dark:text-emerald-500 font-bold mb-3"><i class="bi bi-calendar-plus"></i> Iniciar Cronograma de Cultura</h5>
                <form method="post" action=".">
                    <input type="hidden" name="acao" value="gravar_safra">
    `;

  html += `                    <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
                        <div>
                            <label class="text-xs font-semibold text-ncs-900 dark:text-ncs-50 mb-1.5 block">Identificador da Safra:</label>
                            <input type="text" name="nome_safra" required
                                   class="w-full px-3 py-2 bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded-md text-ncs-900 dark:text-ncs-50 focus:ring-1 focus:ring-emerald-500 focus:outline-none transition-all duration-150 placeholder:text-ncs-900/50" 
                                   placeholder="Ex: Safra Café 2026/2027">
                        </div>
                        <div>
                            <label class="text-xs font-semibold text-ncs-900 dark:text-ncs-50 mb-1.5 block">Cultura / Cultivar:</label>
                            <input type="text" name="cultura" required
                                   class="w-full px-3 py-2 bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded-md text-ncs-900 dark:text-ncs-50 focus:ring-1 focus:ring-emerald-500 focus:outline-none transition-all duration-150 placeholder:text-ncs-900/50" 
                                   placeholder="Ex: Café Catuaí Vermelho">
                        </div>
                        <div>
                            <label class="text-xs font-semibold text-ncs-900 dark:text-ncs-50 mb-1.5 block">Data do Plantio:</label>
                            <input type="date" name="data_plantio" required
                                   class="w-full px-3 py-2 bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded-md text-ncs-900 dark:text-ncs-50 focus:ring-1 focus:ring-emerald-500 focus:outline-none transition-all duration-150">
                        </div>
                        <div>
                            <label class="text-xs font-semibold text-ncs-900 dark:text-ncs-50 mb-1.5 block">Área Alocada (Ha):</label>
                            <input type="number" step="0.1" name="area_ha" required
                                   class="w-full px-3 py-2 bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded-md text-ncs-900 dark:text-ncs-50 focus:ring-1 focus:ring-emerald-500 focus:outline-none transition-all duration-150 placeholder:text-ncs-900/50" 
                                   placeholder="Ex: 15.5">
                        </div>
    `;

  html += `                        <div class="md:col-span-4 text-right pt-2">
                            <button type="submit" 
                                    class="px-5 py-2 font-medium text-white bg-emerald-600 dark:bg-emerald-700 border border-emerald-600 dark:border-emerald-700 rounded-md hover:bg-emerald-700 dark:hover:bg-emerald-600 transition-all duration-150">
                                Salvar Planejamento
                            </button>
                        </div>
                    </div>
                </form>
            </div>
        </div>

        <!-- Cards de estatísticas - Bento Grid -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-colors duration-200">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase block">Safras Ativas em Campo</span>
                <h3 class="text-xl font-bold text-ncs-900 dark:text-ncs-50 my-1">${safras.length || 0}</h3>
                <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium block">Culturas em monitoramento</small>
            </div>
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-colors duration-200">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase block mb-2">Área Total Cultivada</span>
                <h3 class="text-xl font-bold text-emerald-600 dark:text-emerald-500 my-1">${area_total ? area_total.toFixed(1) : '0.0'} Ha</h3>
                <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium block">Soma de talhões mapeados</small>
            </div>
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-colors duration-200">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase block mb-2">Status de Planejamento</span>
                <h3 class="text-xl font-bold text-emerald-600 dark:text-emerald-500 my-1">Regular</h3>
                <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium block">Janelas de plantio integradas</small>
            </div>
        </div>
    `;

  // Janelas Inteligentes - SKILL PREVISÃO AGRONÔMICA (lista vazia)
  html += `        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 mb-4 shadow-none transition-colors duration-200">
            <div class="flex items-center justify-between mb-3">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase"><i class="bi bi-cpu"></i> Inteligência de Plantio e Colheita</span>
                <span class="px-2 py-1 text-xs font-bold rounded-md bg-emerald-600 dark:bg-emerald-700 text-white">Clima + histórico + cultura</span>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
    `;

  if (janelas_inteligentes.length > 0) {
    janelas_inteligentes.forEach((janela) => {
      html += `                <div class="border border-ncs-900/30 dark:border-ncs-50/30 rounded-md p-4 transition-colors duration-200">
                    <div class="flex items-start justify-between mb-2">
                        <div>
                            <h6 class="font-bold text-ncs-900 dark:text-ncs-50 mb-0.5 text-sm">${janela.safra}</h6>
                            <small class="text-ncs-900/50 dark:text-ncs-900/50 text-xs block">${janela.cultura} - score operacional ${janela.score}%</small>
                        </div>
                        <span class="px-2 py-1 text-xs font-bold rounded-md bg-slate-200 dark:bg-ncs-900/80 text-ncs-900 dark:text-ncs-50">Pendente</span>
                    </div>
                    <div class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 mb-1">
                        <span class="block">Plantio sugerido:</span>
                        <span class="text-emerald-600 dark:text-emerald-400">${janela.plantio_inicio} a ${janela.plantio_fim}</span>
                    </div>
                    <div class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70">
                        <span class="block">Colheita estimada:</span>
                        <span class="text-blue-600 dark:text-blue-400">${janela.colheita_inicio} a ${janela.colheita_fim}</span>
                    </div>
                </div>
    `;
    });
  } else {
    html += `                <div class="md:col-span-2 text-center text-ncs-900/50 dark:text-ncs-900/50 text-xs font-bold py-3">Cadastre uma safra para ativar recomendações operacionais.</div>
    `;
  }

  html += `            </div>
        </div>
    `;

  // Tabela de Safras (lista vazia)
  html += `        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-colors duration-200">
            <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase block mb-3"><i class="bi bi-journal-text"></i> Lista de Culturas e Lançamentos Agrícolas Ativos</span>
            <div class="overflow-x-auto">
                <table class="w-full text-sm">
                    <thead class="bg-ncs-50/80 dark:bg-ncs-900/50">
                        <tr class="text-ncs-900/70 dark:text-ncs-50/70 text-xs uppercase tracking-wider">
                            <th class="text-left font-medium py-2 px-3">Identificador Safra</th>
                            <th class="font-medium py-2 px-3">Cultura Especificada</th>
                            <th class="font-medium py-2 px-3">Data de Plantio</th>
                            <th class="font-medium py-2 px-3">Área Alocada</th>
                            <th class="font-medium py-2 px-3">Status Operacional</th>
                            <th class="font-medium py-2 px-3">Ações</th>
                        </tr>
                    </thead>
                    <tbody class="text-ncs-900 dark:text-ncs-50 divide-y divide-ncs-900/20 dark:divide-ncs-50/20/80">
    `;

  if (safras.length > 0) {
    safras.forEach((safra) => {
      html += `                        <tr>
                <td class="font-bold text-ncs-900 dark:text-ncs-50 py-2 px-3 text-left"><strong>${safra.nome_safra}</strong></td>
                <td class="py-2 px-3 text-center"><span class="px-2 py-0.5 font-bold rounded-md bg-ncs-50/80 dark:bg-ncs-900/80 text-ncs-900 dark:text-ncs-50 text-xs inline-block">${safra.cultura}</span></td>
                <td class="py-2 px-3 text-center">${safra.data_inicio_prevista || safra.data_plantio || 'Não informada'}</td>
                <td class="py-2 px-3 text-center">${safra.area_ha ? parseFloat(safra.area_ha).toFixed(1) : '0.0'} Ha</td>
                <td class="py-2 px-3 text-center"><span class="px-2 py-0.5 font-bold rounded-md bg-emerald-600 dark:bg-emerald-700 text-white text-xs inline-block">Em Desenvolvimento</span></td>
                <td class="py-2 px-3 text-center">
                    <form method="post" action="." onsubmit="return confirm('Deseja realmente remover esta safra do planejamento agrícola?');" class="inline">
                        <input type="hidden" name="acao" value="excluir_safra">
                        <input type="hidden" name="id_safra" value="${safra.id}">
                        <button type="submit" class="px-2.5 py-1 text-xs font-bold rounded-md border border-red-300 dark:border-red-700 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 transition-all duration-150">Excluir</button>
                    </form>
                </td>
            </tr>
    `;
    });
  } else {
    html += `                        <tr>
                <td colspan="6" class="py-4 text-center text-ncs-900/50 dark:text-ncs-900/50 font-bold">Nenhum planejamento agrícola ou safra ativa registrada no banco de dados.</td>
            </tr>
    `;
  }

  html += `                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', function() {
            // Scripts iniciais
        });
    </script>
    `;

  return html;
}

// Exportação de funções para o SPA
window.renderAgendaTab = renderAgendaTab;
window.renderAgendaAnalisesTab = renderAgendaAnalisesTab;
window.renderAgendaProducaoTab = renderAgendaProducaoTab;
window.abrirModalTarefa = abrirModalTarefa;
window.fecharModalTarefa = fecharModalTarefa;
window.filtrarAgendaPorCargo = filtrarAgendaPorCargo;
