'use strict';

// ============================================
// FUNÇÃO PARA FECHAR MODAL EMPREGADO
// ============================================
function fecharModalEmpregado() {
  const backdrop = document.getElementById('modalNovoEmpregadoBackdrop');
  if (backdrop) {
    backdrop.classList.add('hidden');
    backdrop.classList.remove('flex');
  }
}

// ============================================
// FUNÇÃO PARA ABRIR MODAL EMPREGADO
// ============================================
function abrirModalEmpregado() {
  const backdrop = document.getElementById('modalNovoEmpregadoBackdrop');
  if (backdrop) {
    backdrop.classList.remove('hidden');
    backdrop.classList.add('flex');
  }
}

// ============================================
// FUNÇÃO PARA FILTRAR EMPREGADOS
// ============================================
function filtrarEmpregados() {
  const busca = document.getElementById('buscaEmpregado');
  const valor = busca ? busca.value.toLowerCase() : '';
  console.log('Filtrando empregados por:', valor);
}

// ============================================
// FUNÇÃO PARA FILTRAR POR CARGO
// ============================================
function filtrarPorCargo() {
  const cargosSelecionados = [];
  const checkboxes = document.querySelectorAll('input[name="cargos_filtro"]:checked');
  checkboxes.forEach((cb) => {
    cargosSelecionados.push(parseInt(cb.value));
  });
  console.log('Filtrando por cargos:', cargosSelecionados);
}

// ============================================
// FUNÇÃO PARA EDITAR EMPREGADO
// ============================================
function editarEmpregado(id) {
  console.log('Editando empregado ID:', id);
}

// ============================================
// FUNÇÃO PARA REMOVER EMPREGADO
// ============================================
function removerEmpregado(id) {
  console.log('Removendo empregado ID:', id);
}

// ============================================
// EMPREGADOS TAB - RENDER COM SHADCN UI / BENTO GRID CONCEPT
// ============================================
function renderEmpregadosTab(data) {
  const mensagens = data && data.mensagens ? data.mensagens : null;
  const busca_nome = data && data.busca_nome ? data.busca_nome : '';
  const cargos = data && data.cargos ? data.cargos : [];
  const cargos_filtrados = data && data.cargos_filtrados ? data.cargos_filtrados : [];
  const funcionarios = data && data.funcionarios ? data.funcionarios : [];

  // Cargo ativo padrão para filtro
  const cargoSelecionado =
    cargos_filtrados.length > 0
      ? cargos.find((c) => cargos_filtrados.includes(c.id))?.nome || 'Todos os Cargos'
      : 'Todos os Cargos';

  let html = `<div class="px-6 py-5 space-y-5 bg-ncs-50 dark:bg-ncs-900 min-h-screen text-ncs-900 dark:text-ncs-50">
        
        <!-- Barra Superior de Ferramentas - Bento Grid -->
        <div class="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4">
            
            <!-- Input de Busca com Ícone -->
            <div class="lg:col-span-1">
                <div class="relative">
                    <i class="bi bi-search absolute left-3 top-1/2 -translate-y-1/2 text-ncs-900/50 dark:text-ncs-900/50 pointer-events-none"></i>
                    <input type="text" id="buscaEmpregado" value="${busca_nome}" 
                           class="w-full pl-9 pr-3 py-2 bg-white dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded-md text-ncs-900 dark:text-ncs-50 focus:ring-1 focus:ring-emerald-500 focus:outline-none transition-all duration-150 placeholder:text-ncs-900/50" 
                           placeholder="Buscar por nome..." onkeyup="filtrarEmpregados()">
                </div>
            </div>
            
            <!-- Dropdown Minimalista de Cargos -->
            <div class="lg:col-span-1 relative">
                <button type="button" id="btnDropdownCargos" 
                        class="w-full px-3 py-2 bg-white dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded-md text-ncs-900 dark:text-ncs-50 text-sm font-medium hover:bg-ncs-50/80 dark:hover-bg-ncs-900/80 transition-all duration-150 flex items-center justify-between">
                    <span>${cargoSelecionado}</span>
                    <i class="bi bi-chevron-down text-ncs-900/50 dark:text-ncs-900/50"></i>
                </button>
                <div id="dropdownCargosMenu" class="absolute top-full left-0 mt-1 hidden bg-white dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded-md shadow-none p-3 min-w-[280px] z-50 transition-all duration-200 max-h-80 overflow-y-auto">
                    <div class="grid grid-cols-1 gap-2">
        `;

  // Cargos no dropdown - usando forEach com formatação clean
  cargos.forEach((c) => {
    const checked = cargos_filtrados.includes(c.id) ? 'checked' : '';
    html += `                        <label class="flex items-center px-2 py-1.5 rounded hover:bg-ncs-50 dark:hover:bg-ncs-900 cursor-pointer transition-all duration-150">
                            <input class="w-4 h-4 mr-2.5 text-emerald-600 dark:text-emerald-500 bg-white dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded focus:ring-emerald-500" 
                                   type="checkbox" name="cargos_filtro" value="${c.id}" id="c-${c.id}" ${checked} onchange="filtrarPorCargo()">
                            <span class="text-sm text-ncs-900 dark:text-ncs-50 truncate">${c.nome}</span>
                        </label>
        `;
  });

  html += `                    </div>
                </div>
            </div>
            
            <!-- Botão Tático Esmeralda - Incluir Individual -->
            <div class="lg:col-span-1">
                <button type="button" id="btnIncluirEmpregado" 
                        class="w-full px-4 py-2 font-medium text-white bg-emerald-600 dark:bg-emerald-700 border border-emerald-600 dark:border-emerald-700 rounded-md hover:bg-emerald-700 dark:hover:bg-emerald-600 transition-all duration-150 flex items-center justify-center gap-2">
                    <i class="bi bi-person-plus-fill"></i> Incluir Individual
                </button>
            </div>
            
            <!-- Botão de Exportação -->
            <div class="lg:col-span-1">
                <a href="?export=xlsx" class="w-full flex items-center justify-center gap-2 px-4 py-2 font-medium text-sm rounded-md bg-ncs-50/80 dark:bg-ncs-900/80 text-ncs-900 dark:text-ncs-50 hover:bg-slate-200 dark:hover:bg-ncs-900/80 transition-all duration-150">
                    <i class="bi bi-download"></i> Baixar Planilha Modelo
                </a>
            </div>
        </div>

    `;

  // Mensagem de sucesso (se houver)
  if (mensagens) {
    html += `        <div class="bg-emerald-50 dark:bg-emerald-900/30 border border-emerald-200 dark:border-emerald-800 rounded-md py-3 px-4 text-emerald-800 dark:text-emerald-200 text-sm font-medium">
            ${mensagens}
        </div>
    `;
  }

  // Card de Tabela - Estilizada profissionalmente com Bento Grid (sem fundo branco fantasma)
  html += `        <div class="bg-white dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md shadow-none transition-colors duration-200">
            <div class="overflow-x-auto">
                <table class="w-full text-sm">
                    <thead class="bg-ncs-50/80 dark:bg-ncs-900/50 text-ncs-900/50 dark:text-ncs-900/50 font-mono text-xs uppercase tracking-wider">
                        <tr class="border-b border-ncs-900/20 dark:border-ncs-50/20/80">
                            <th class="text-left font-medium py-3 px-4">ID</th>
                            <th class="text-left font-medium py-3 px-4">Nome do Funcionário</th>
                            <th class="text-left font-medium py-3 px-4">Cargo / Função</th>
                            <th class="text-left font-medium py-3 px-4">Salário</th>
                            <th class="text-left font-medium py-3 px-4">Carga Horária</th>
                            <th class="text-left font-medium py-3 px-4">EPIs Homologados</th>
                            <th class="text-center font-medium py-3 px-4">Ações</th>
                        </tr>
                    </thead>
                    <tbody class="text-ncs-900 dark:text-ncs-50 divide-y divide-ncs-900/20 dark:divide-slate-800/80">
        `;

  // Funcionários - renderização dinâmica
  if (funcionarios.length > 0) {
    funcionarios.forEach((f) => {
      const episFormatados =
        f.epis && f.epis.length > 0 ? f.epis.join(', ') : f.historico_epis || f.epis || 'N/A';

      html += `                        <tr class="hover:bg-ncs-50 dark:hover:bg-ncs-900/30 transition-all duration-150">
                            <td class="py-3 px-4 font-mono text-xs text-ncs-900/50 dark:text-ncs-900/50">#${f.id || '---'}</td>
                            <td class="py-3 px-4 font-semibold text-ncs-900 dark:text-ncs-50">${f.nome || f.name || 'Não informado'}</td>
                            <td class="py-3 px-4">
                                <span class="inline-block px-2 py-0.5 text-xs font-medium rounded-md bg-emerald-100 dark:bg-emerald-900/50 text-emerald-800 dark:text-emerald-200">${f.cargo_nome || f.cargo || 'Não informado'}</span>
                            </td>
                            <td class="py-3 px-4 text-emerald-600 dark:text-emerald-400 font-semibold">R$ ${(f.salario || f.salary || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</td>
                            <td class="py-3 px-4 text-ncs-900/70 dark:text-ncs-50/70">${f.carga_horaria || 44}h / sem</td>
                            <td class="py-3 px-4 text-ncs-900/70 dark:text-ncs-50/70 text-xs max-w-[280px] truncate">${episFormatados}</td>
                            <td class="py-3 px-4 text-center">
                                <button type="button" onclick="editarEmpregado(${f.id})" 
                                        class="inline-flex items-center justify-center w-8 h-8 rounded-md border border-ncs-900/30 dark:border-ncs-50/30 bg-white dark:bg-ncs-900 text-ncs-900/70 dark:text-ncs-50/70 hover:bg-ncs-50/80 dark:hover-bg-ncs-900/80 transition-all duration-150">
                                    <i class="bi bi-pencil text-xs"></i>
                                </button>
                                <button type="button" onclick="removerEmpregado(${f.id})" 
                                        class="inline-flex items-center justify-center w-8 h-8 rounded-md border border-red-300 dark:border-red-700 bg-white dark:bg-ncs-900 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 transition-all duration-150 ml-1">
                                    <i class="bi bi-trash text-xs"></i>
                                </button>
                            </td>
                        </tr>
        `;
    });
  } else {
    html += `                        <tr>
                            <td colspan="7" class="py-8 text-center text-ncs-900/50 dark:text-ncs-900/50 font-medium">
                                <i class="bi bi-person-x text-3xl opacity-30 mb-2 block"></i>
                                Nenhum funcionário ativo nesta fazenda. Utilize os botões superiores para cadastrar.
                            </td>
                        </tr>
        `;
  }

  html += `                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- Modal de Inclusão de Colaboradores - 100% Adaptativo Shadcn UI -->
    <div class="fixed inset-0 bg-black/50 dark:bg-black/70 z-50 items-center justify-center hidden transition-all duration-200" id="modalNovoEmpregadoBackdrop">
        <div class="bg-white dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto transition-colors duration-200" id="modalNovoEmpregado">
            <div class="flex items-center justify-between px-5 py-4 border-b border-ncs-900/20 dark:border-ncs-50/20/80 bg-emerald-600 dark:bg-emerald-700 rounded-t-md">
                <h5 class="text-lg font-bold text-white m-0 flex items-center gap-2"><i class="bi bi-person-plus"></i> Registrar Colaborador</h5>
                <button type="button" onclick="fecharModalEmpregado()" class="text-white text-xl font-medium hover:opacity-80 transition-opacity">&times;</button>
            </div>
            <form method="post" action=".">
                <input type="hidden" name="acao" value="cadastrar_manual">
                <div class="p-5 bg-ncs-50 dark:bg-ncs-900">
                    
                    <div class="mb-4">
                        <label class="text-xs font-semibold text-ncs-900 dark:text-ncs-50 mb-1.5 block">Nome Completo:</label>
                        <input type="text" name="nome" required
                               class="w-full px-3 py-2 bg-white dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded-md text-ncs-900 dark:text-ncs-50 focus:ring-1 focus:ring-emerald-500 focus:outline-none transition-all duration-150 placeholder:text-ncs-900/50" 
                               placeholder="Ex: João Silva">
                    </div>

                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                        <div>
                            <label class="text-xs font-semibold text-ncs-900 dark:text-ncs-50 mb-1.5 block">Cargo / Função:</label>
                            <select name="cargo" required
                                    class="w-full px-3 py-2 bg-white dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded-md text-ncs-900 dark:text-ncs-50 focus:ring-1 focus:ring-emerald-500 focus:outline-none transition-all duration-150">
                                <option value="">Selecione um cargo...</option>
        `;

  // Cargos no select do modal
  cargos.forEach((c) => {
    html += `                                <option value="${c.id}">${c.nome}</option>
        `;
  });

  html += `                            </select>
                        </div>
                        <div>
                            <label class="text-xs font-semibold text-ncs-900 dark:text-ncs-50 mb-1.5 block">Salário Mensal:</label>
                            <input type="number" step="0.01" name="salario" required
                                   class="w-full px-3 py-2 bg-white dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded-md text-ncs-900 dark:text-ncs-50 focus:ring-1 focus:ring-emerald-500 focus:outline-none transition-all duration-150 placeholder:text-ncs-900/50" 
                                   placeholder="1500.00">
                        </div>
                    </div>

                    <div class="mb-4">
                        <label class="text-xs font-semibold text-ncs-900 dark:text-ncs-50 mb-1.5 block">Carga Horária Semanal:</label>
                        <input type="number" name="carga_horaria" value="44" required
                               class="w-full px-3 py-2 bg-white dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded-md text-ncs-900 dark:text-ncs-50 focus:ring-1 focus:ring-emerald-500 focus:outline-none transition-all duration-150">
                    </div>

                    <div class="mb-4">
                        <label class="text-xs font-semibold text-ncs-900 dark:text-ncs-50 mb-2 block">EPIs de Campo Entregues:</label>
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
                            <label class="flex items-center py-1.5 px-1 rounded hover:bg-ncs-50/80 dark:hover-bg-ncs-900/80 cursor-pointer transition-all duration-150">
                                <input class="w-4 h-4 mr-2.5 text-emerald-600 dark:text-emerald-500 bg-white dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded focus:ring-emerald-500" 
                                       type="checkbox" name="epis_selecionados" value="Botas" id="epi1">
                                <span class="text-xs text-ncs-900 dark:text-ncs-50">Botas de Segurança</span>
                            </label>
                            <label class="flex items-center py-1.5 px-1 rounded hover:bg-ncs-50/80 dark:hover-bg-ncs-900/80 cursor-pointer transition-all duration-150">
                                <input class="w-4 h-4 mr-2.5 text-emerald-600 dark:text-emerald-500 bg-white dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded focus:ring-emerald-500" 
                                       type="checkbox" name="epis_selecionados" value="Óculos" id="epi2">
                                <span class="text-xs text-ncs-900 dark:text-ncs-50">Óculos de Proteção</span>
                            </label>
                            <label class="flex items-center py-1.5 px-1 rounded hover:bg-ncs-50/80 dark:hover-bg-ncs-900/80 cursor-pointer transition-all duration-150">
                                <input class="w-4 h-4 mr-2.5 text-emerald-600 dark:text-emerald-500 bg-white dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded focus:ring-emerald-500" 
                                       type="checkbox" name="epis_selecionados" value="Luvas de Raspa" id="epi3">
                                <span class="text-xs text-ncs-900 dark:text-ncs-50">Luvas de Raspa</span>
                            </label>
                            <label class="flex items-center py-1.5 px-1 rounded hover:bg-ncs-50/80 dark:hover-bg-ncs-900/80 cursor-pointer transition-all duration-150">
                                <input class="w-4 h-4 mr-2.5 text-emerald-600 dark:text-emerald-500 bg-white dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded focus:ring-emerald-500" 
                                       type="checkbox" name="epis_selecionados" value="Protetor Auricular" id="epi4">
                                <span class="text-xs text-ncs-900 dark:text-ncs-50">Protetor Auricular</span>
                            </label>
                            <label class="flex items-center py-1.5 px-1 rounded hover:bg-ncs-50/80 dark:hover-bg-ncs-900/80 cursor-pointer transition-all duration-150">
                                <input class="w-4 h-4 mr-2.5 text-emerald-600 dark:text-emerald-500 bg-white dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded focus:ring-emerald-500" 
                                       type="checkbox" name="epis_selecionados" value="Avental Impermeável" id="epi5">
                                <span class="text-xs text-ncs-900 dark:text-ncs-50">Avental Impermeável</span>
                            </label>
                            <label class="flex items-center py-1.5 px-1 rounded hover:bg-ncs-50/80 dark:hover-bg-ncs-900/80 cursor-pointer transition-all duration-150">
                                <input class="w-4 h-4 mr-2.5 text-emerald-600 dark:text-emerald-500 bg-white dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded focus:ring-emerald-500" 
                                       type="checkbox" name="epis_selecionados" value="Máscara contra poeira" id="epi6">
                                <span class="text-xs text-ncs-900 dark:text-ncs-50">Máscara contra poeira</span>
                            </label>
                        </div>
                    </div>

                    <div class="border-t border-ncs-900/20 dark:border-ncs-50/20/80 pt-4 mt-4">
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                                <label class="text-xs font-semibold text-ncs-900 dark:text-ncs-50 mb-1.5 block">Usuário de Acesso:</label>
                                <input type="text" name="usuario" required
                                       class="w-full px-3 py-2 bg-white dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded-md text-ncs-900 dark:text-ncs-50 focus:ring-1 focus:ring-emerald-500 focus:outline-none transition-all duration-150 placeholder:text-ncs-900/50" 
                                       placeholder="joao.silva">
                            </div>
                            <div>
                                <label class="text-xs font-semibold text-ncs-900 dark:text-ncs-50 mb-1.5 block">Senha Provisória:</label>
                                <input type="password" name="senha" required
                                       class="w-full px-3 py-2 bg-white dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded-md text-ncs-900 dark:text-ncs-50 focus:ring-1 focus:ring-emerald-500 focus:outline-none transition-all duration-150 placeholder:text-ncs-900/50" 
                                       placeholder="123456">
                            </div>
                        </div>
                    </div>

                </div>
                <div class="flex items-center justify-end gap-2 px-5 py-3 border-t border-ncs-900/20 dark:border-ncs-50/20/80 bg-ncs-50/80 dark:bg-ncs-900 rounded-b-md">
                    <button type="button" onclick="fecharModalEmpregado()" 
                            class="px-4 py-2 font-medium text-ncs-900 dark:text-ncs-50 bg-white dark:bg-ncs-900 border border-ncs-900/30 dark:border-ncs-50/30 rounded-md hover:bg-ncs-50 dark:hover:bg-ncs-900 transition-all duration-150">
                        Fechar
                    </button>
                    <button type="submit" 
                            class="px-4 py-2 font-medium text-white bg-emerald-600 dark:bg-emerald-700 border border-emerald-600 dark:border-emerald-700 rounded-md hover:bg-emerald-700 dark:hover:bg-emerald-600 transition-all duration-150">
                        Salvar Colaborador
                    </button>
                </div>
            </form>
        </div>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const btnDropdown = document.getElementById('btnDropdownCargos');
            const dropdownMenu = document.getElementById('dropdownCargosMenu');
            
            if (btnDropdown && dropdownMenu) {
                btnDropdown.addEventListener('click', function(e) {
                    e.stopPropagation();
                    dropdownMenu.classList.toggle('hidden');
                });
                
                document.addEventListener('click', function(e) {
                    if (!dropdownMenu.contains(e.target) && !btnDropdown.contains(e.target)) {
                        dropdownMenu.classList.add('hidden');
                    }
                });
            }
            
            const btnIncluir = document.getElementById('btnIncluirEmpregado');
            if (btnIncluir) {
                btnIncluir.addEventListener('click', abrirModalEmpregado);
            }
        });
    </script>
    `;

  return html;
}

// Exportação de funções para o SPA
window.renderEmpregadosTab = renderEmpregadosTab;
window.abrirModalEmpregado = abrirModalEmpregado;
window.fecharModalEmpregado = fecharModalEmpregado;
window.filtrarEmpregados = filtrarEmpregados;
window.filtrarPorCargo = filtrarPorCargo;
window.editarEmpregado = editarEmpregado;
window.removerEmpregado = removerEmpregado;
