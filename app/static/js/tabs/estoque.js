'use strict';

function renderEstoqueTab(data) {
  const insumos = data && data.insumos ? data.insumos : [];
  const entradas = data && data.entradas ? data.entradas : [];
  const saidas = data && data.saidas ? data.saidas : [];

  let html = `<div class="px-6 py-5 space-y-5 bg-ncs-50 dark:bg-ncs-900 min-h-screen text-ncs-900 dark:text-ncs-50">

        <!-- Cabeçalho Tático Integrado - Bento Grid Style -->
        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
            <div class="flex items-center gap-3 mb-2">
                <span class="px-3 py-1.5 text-xs font-medium rounded-md bg-emerald-100 dark:bg-emerald-900/50 text-emerald-800 dark:text-emerald-200"><i class="bi bi-box-seam"></i> Rastreabilidade ativa</span>
            </div>
            <h3 class="text-xl font-bold text-ncs-900 dark:text-ncs-50 mb-1 font-mono">Controladoria de Estoque e Rastreabilidade Operacional</h3>
            <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium"><i class="bi bi-shield-check text-emerald-600 dark:text-emerald-500"></i> Monitoramento de insumos, lotes, fornecedores e movimentações fiscais em tempo real</small>
        </div>

        <!-- Tabs Navigation - Bento Style -->
        <div class="flex flex-wrap gap-2 border-b border-ncs-900/20 dark:border-ncs-50/20">
            <button type="button" onclick="switchEstoqueTab('inventario')" id="tab-inventario" class="px-4 py-2 text-sm font-medium rounded-md bg-emerald-600 text-white transition-all duration-150 border border-ncs-900/30 shadow-none">Inventário de Insumos</button>
            <button type="button" onclick="switchEstoqueTab('entradas')" id="tab-entradas" class="px-4 py-2 text-sm font-medium rounded-md bg-ncs-900 text-ncs-50 dark:text-ncs-900 border border-ncs-50/20 hover:bg-ncs-900/80 hover:text-emerald-500 transition-all duration-150 font-mono">Rastreabilidade de Entradas</button>
            <button type="button" onclick="switchEstoqueTab('saidas')" id="tab-saidas" class="px-4 py-2 text-sm font-medium rounded-md bg-ncs-900 text-ncs-50 dark:text-ncs-900 border border-ncs-50/20 hover:bg-ncs-900/80 hover:text-emerald-500 transition-all duration-150 font-mono">Tráfego de Saídas</button>
        </div>

        <!-- Inventário Tab -->
        <div id="estoque-inventario" class="estoque-tab-content">
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md overflow-hidden">
                <div class="max-h-[500px] overflow-y-auto">
                    <table class="w-full text-sm font-mono">
                        <thead class="bg-ncs-50/80 dark:bg-ncs-900/50 border-b border-ncs-900/20 dark:border-ncs-50/20">
                            <tr class="text-ncs-900/70 dark:text-ncs-50/70 text-xs uppercase tracking-wider">
                                <th class="text-left font-medium pb-2 pl-4">Insumo</th>
                                <th class="font-medium pb-2">Marca</th>
                                <th class="font-medium pb-2">Lote</th>
                                <th class="text-right font-medium pb-2 pr-4">Volume</th>
                                <th class="text-center font-medium pb-2 pr-4">Ações</th>
                            </tr>
                        </thead>
                        <tbody class="text-ncs-900 dark:text-ncs-50 divide-y divide-ncs-900/20 dark:divide-ncs-50/20">
        `;

  // Insumos - usando forEach - sem dados estáticos hardcoded
  if (insumos.length > 0) {
    insumos.forEach((i) => {
      html += `                        <tr class="hover:bg-ncs-50/80 dark:hover:bg-ncs-900/50 transition-colors">
                            <td class="font-semibold text-ncs-900 dark:text-ncs-50 py-3 pl-4">${i.nome || 'Item'}</td>
                            <td class="text-center py-3">${i.marca || '-'}</td>
                            <td class="text-center py-3 font-mono"><code class="bg-ncs-50/80 dark:bg-ncs-900/50 px-1.5 py-0.5 rounded">${i.lote || '-'}</code></td>
                            <td class="text-right text-ncs-900 dark:text-ncs-50 py-3 pr-4">${i.quantidade_estoque || i.quantidade || 0} un</td>
                            <td class="text-center py-3 pr-4">
                                <button type="button" onclick="editarEstoque(${i.id || 0})" class="px-3 py-1.5 text-xs font-medium rounded-md border border-ncs-900/30 dark:border-ncs-50/30 bg-ncs-900 dark:bg-ncs-900 text-ncs-50 dark:text-ncs-900 hover:bg-ncs-900/80 dark:hover:bg-ncs-900/80 hover:border-emerald-500/50 transition-all duration-150 font-mono">Editar</button>
                            </td>
                        </tr>
        `;
    });
  } else {
    html += `                        <tr>
                            <td colspan="5" class="text-center text-ncs-900/70 dark:text-ncs-50/70 py-8 font-medium font-mono">Nenhum registro localizado no momento.</td>
                        </tr>
        `;
  }

  html += `                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Entradas Tab -->
        <div id="estoque-entradas" class="estoque-tab-content hidden">
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md overflow-hidden">
                <div class="max-h-[500px] overflow-y-auto">
                    <table class="w-full text-sm font-mono">
                        <thead class="bg-ncs-50/80 dark:bg-ncs-900/50 border-b border-ncs-900/20 dark:border-ncs-50/20">
                            <tr class="text-ncs-900/70 dark:text-ncs-50/70 text-xs uppercase tracking-wider">
                                <th class="text-left font-medium pb-2 pl-4">Fornecedor</th>
                                <th class="font-medium pb-2">CNPJ / CPF</th>
                                <th class="font-medium pb-2">Categoria</th>
                                <th class="text-right font-medium pb-2 pr-4">Histórico</th>
                            </tr>
                        </thead>
                        <tbody class="text-ncs-900 dark:text-ncs-50 divide-y divide-ncs-900/20 dark:divide-ncs-50/20">
        `;

  // Entradas - usando forEach - sem dados estáticos hardcoded
  if (entradas.length > 0) {
    entradas.forEach((f) => {
      html += `                        <tr class="hover:bg-ncs-50/80 dark:hover:bg-ncs-900/50 transition-colors">
                            <td class="font-semibold text-ncs-900 dark:text-ncs-50 py-3 pl-4">${f.razao_social || f.nome || '-'}</td>
                            <td class="text-center py-3 font-mono"><code class="bg-ncs-50/80 dark:bg-ncs-900/50 px-1.5 py-0.5 rounded">${f.cnpj_cpf || f.cnpj || '-'}</code></td>
                            <td class="text-center py-3">${f.tipo_produto || f.categoria || '-'}</td>
                            <td class="text-right py-3 pr-4 font-mono"><small>${f.historico_compras || f.historico || 'N/A'}</small></td>
                        </tr>
        `;
    });
  } else {
    html += `                        <tr>
                            <td colspan="4" class="text-center text-ncs-900/70 dark:text-ncs-50/70 py-8 font-medium font-mono">Nenhum registro localizado no momento.</td>
                        </tr>
        `;
  }

  html += `                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Saídas Tab -->
        <div id="estoque-saidas" class="estoque-tab-content hidden">
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md overflow-hidden">
                <div class="max-h-[500px] overflow-y-auto">
                    <table class="w-full text-sm font-mono">
                        <thead class="bg-ncs-50/80 dark:bg-ncs-900/50 border-b border-ncs-900/20 dark:border-ncs-50/20">
                            <tr class="text-ncs-900/70 dark:text-ncs-50/70 text-xs uppercase tracking-wider">
                                <th class="text-left font-medium pb-2 pl-4">Nota Fiscal</th>
                                <th class="font-medium pb-2">Cliente</th>
                                <th class="font-medium pb-2">Origem</th>
                                <th class="text-right font-medium pb-2 pr-4">Volume</th>
                                <th class="text-right font-medium pb-2 pr-4">Faturamento</th>
                            </tr>
                        </thead>
                        <tbody class="text-ncs-900 dark:text-ncs-50 divide-y divide-ncs-900/20 dark:divide-ncs-50/20">
        `;

  // Saídas - usando forEach - sem dados estáticos hardcoded
  if (saidas.length > 0) {
    saidas.forEach((v) => {
      html += `                        <tr class="hover:bg-ncs-50/80 dark:hover:bg-ncs-900/50 transition-colors">
                            <td class="font-semibold text-ncs-900 dark:text-ncs-50 py-3 pl-4 font-mono"><code class="bg-ncs-50/80 dark:bg-ncs-900/50 px-1.5 py-0.5 rounded">${v.nota_fiscal || '-'}</code></td>
                            <td class="text-center py-3 font-mono">${v.cliente || '-'}</td>
                            <td class="text-center py-3">
                                <span class="px-2 py-1 text-xs font-medium rounded-md bg-emerald-100 dark:bg-emerald-900/50 text-emerald-800 dark:text-emerald-200 border border-emerald-300 dark:border-emerald-700 font-mono">${v.tipo_produto || 'Grãos'}</span>
                            </td>
                            <td class="text-right text-ncs-900 dark:text-ncs-50 py-3 pr-4 font-mono">${v.quantidade_vendida || v.quantidade || 0} sacas</td>
                            <td class="text-right font-semibold text-emerald-600 dark:text-emerald-500 py-3 pr-4 font-mono">R$ ${parseFloat(v.valor_total || v.valor || 0).toFixed(2)}</td>
                        </tr>
        `;
    });
  } else {
    html += `                        <tr>
                            <td colspan="5" class="text-center text-ncs-900/70 dark:text-ncs-50/70 py-8 font-medium font-mono">Nenhum registro localizado no momento.</td>
                        </tr>
        `;
  }

  html += `                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Inicializa a aba padrão
        document.addEventListener('DOMContentLoaded', function() {
            switchEstoqueTab('inventario');
        });
    </script>

    <style>
        /* Estilo dos cards */
        .analytics-card {
            border-radius: 16px;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .analytics-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 24px rgba(0, 0, 0, 0.08);
        }
        body.dark-mode .analytics-card {
            background: #1e293b;
            color: #e2e8f0;
        }
    </style>
    `;

  return html;
}

function switchEstoqueTab(tabName) {
  // Esconde todos os conteúdos
  document.querySelectorAll('.estoque-tab-content').forEach((el) => {
    el.classList.add('hidden');
  });

  // Mostra o conteúdo selecionado
  const target = document.getElementById('estoque-' + tabName);
  if (target) {
    target.classList.remove('hidden');
  }

  // Atualiza estilos dos botões
  document.querySelectorAll('[id^="tab-"]').forEach((btn) => {
    btn.classList.remove('bg-emerald-600', 'text-white');
    btn.classList.add(
      'bg-ncs-900',
      'text-ncs-50',
      'border-ncs-50/20',
      'hover:bg-ncs-900/80',
      'hover:text-emerald-500'
    );
  });

  // Estiliza o botão ativo
  const activeBtn = document.getElementById('tab-' + tabName);
  if (activeBtn) {
    activeBtn.classList.remove(
      'bg-ncs-900',
      'text-ncs-50',
      'border-ncs-50/20',
      'hover:bg-ncs-900/80',
      'hover:text-emerald-500'
    );
    activeBtn.classList.add('bg-emerald-600', 'text-white');
  }
}

function editarEstoque(itemId) {
  console.log('Editando item de estoque ID:', itemId);
}

// Exportação de funções para o SPA
window.renderEstoqueTab = renderEstoqueTab;
window.switchEstoqueTab = switchEstoqueTab;
window.editarEstoque = editarEstoque;
