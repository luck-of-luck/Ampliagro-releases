'use strict';

function renderFinanceiroTab(data) {
  const lancamentos = data && data.lancamentos ? data.lancamentos : [];
  const saldo_atual = data && data.saldo_atual !== undefined ? data.saldo_atual : 0;
  const total_receitas = data && data.total_receitas !== undefined ? data.total_receitas : 0;
  const total_despesas = data && data.total_despesas !== undefined ? data.total_despesas : 0;

  let html = `<div class="px-6 py-5 space-y-5 bg-ncs-50 dark:bg-ncs-900 min-h-screen text-ncs-900 dark:text-ncs-50">

        <!-- Cabeçalho Tático Integrado - Bento Grid Style -->
        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
            <div class="flex items-center gap-3 mb-2">
                <span class="px-3 py-1.5 text-xs font-medium rounded-md bg-emerald-100 dark:bg-emerald-900/50 text-emerald-800 dark:text-emerald-200"><i class="bi bi-cash-coin"></i> Módulo Financeiro</span>
            </div>
            <h3 class="text-xl font-bold text-ncs-900 dark:text-ncs-50 mb-1 font-mono">Fluxo de Caixa Operacional</h3>
            <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium"><i class="bi bi-shield-check text-emerald-600 dark:text-emerald-500"></i> Receitas e despesas da propriedade</small>
        </div>

        <!-- Summary Cards - Bento Grid 3 Colunas -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider block font-mono">Saldo Atual</span>
                <h3 class="text-xl font-bold text-emerald-600 dark:text-emerald-500 my-1">R$ ${(saldo_atual || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</h3>
                <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium block font-mono">Valor disponível para uso</small>
            </div>
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider block font-mono">Total Receitas</span>
                <h3 class="text-xl font-bold text-emerald-600 dark:text-emerald-500 my-1">R$ ${(total_receitas || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</h3>
                <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium block font-mono">Entradas positivas no período</small>
            </div>
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider block font-mono">Total Despesas</span>
                <h3 class="text-xl font-bold text-rose-600 dark:text-rose-500 my-1">R$ ${(total_despesas || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</h3>
                <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium block font-mono">Saídas negativas no período</small>
            </div>
        </div>

        <!-- Bento Grid 3 Colunas: Form + Table -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <!-- Form Card - Bloco Tático Plano -->
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 lg:col-span-1 shadow-none transition-all duration-200">
                <h5 class="text-lg font-bold text-ncs-900 dark:text-ncs-50 mb-4 font-mono">Novo Registro</h5>
                <form method="post" action="." class="space-y-4">
                    <div>
                        <label class="text-sm font-medium text-ncs-900 dark:text-ncs-50 mb-1.5 block font-mono">Tipo:</label>
                        <select id="tipoRegistro" class="w-full rounded-md border border-ncs-900/30 dark:border-ncs-50/30 bg-ncs-50 dark:bg-ncs-900 px-3 py-2 text-ncs-900 dark:text-ncs-50 focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-all">
                            <option value="RECEITA">Receita</option>
                            <option value="DESPESA">Despesa</option>
                        </select>
                    </div>
                    <div>
                        <label class="text-sm font-medium text-ncs-900 dark:text-ncs-50 mb-1.5 block font-mono">Valor (R$):</label>
                        <input type="number" step="0.01" id="valorRegistro" class="w-full rounded-md border border-ncs-900/30 dark:border-ncs-50/30 bg-ncs-50 dark:bg-ncs-900 px-3 py-2 text-ncs-900 dark:text-ncs-50 focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-all" placeholder="0,00">
                    </div>
                    <div>
                        <label class="text-sm font-medium text-ncs-900 dark:text-ncs-50 mb-1.5 block font-mono">Descrição:</label>
                        <input type="text" id="descricaoRegistro" class="w-full rounded-md border border-ncs-900/30 dark:border-ncs-50/30 bg-ncs-50 dark:bg-ncs-900 px-3 py-2 text-ncs-900 dark:text-ncs-50 focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-all" placeholder="Descrição do lançamento">
                    </div>
                    <div>
                        <label class="text-sm font-medium text-ncs-900 dark:text-ncs-50 mb-1.5 block font-mono">Data:</label>
                        <input type="date" id="dataRegistro" class="w-full rounded-md border border-ncs-900/30 dark:border-ncs-50/30 bg-ncs-50 dark:bg-ncs-900 px-3 py-2 text-ncs-900 dark:text-ncs-50 focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-all">
                    </div>
                    <button type="button" onclick="salvarLancamento()" class="w-full rounded-md border border-ncs-900/30 dark:border-ncs-50/30 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-4 py-2 transition-all select-none">Lançar movimento</button>
                </form>
            </div>

            <!-- Table Card - Histórico de Lançamentos -->
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 lg:col-span-2 shadow-none transition-all duration-200">
                <div class="flex items-center justify-between mb-4">
                    <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider font-mono"><i class="bi bi-list-ul"></i> Histórico de lançamentos</span>
                    <span class="px-2.5 py-1 text-xs font-medium rounded-md bg-ncs-50/80 dark:bg-ncs-900/50 text-ncs-900 dark:text-ncs-50 border border-ncs-900/20 dark:border-ncs-900/30 font-mono">${lancamentos.length || 0} registros</span>
                </div>
                <div class="max-h-[400px] overflow-y-auto">
                    <table class="w-full text-sm">
                        <thead class="border-b border-ncs-900/20 dark:border-ncs-50/20">
                            <tr class="text-ncs-900/70 dark:text-ncs-50/70 font-mono text-xs uppercase">
                                <th class="text-left font-medium pb-2 px-3">Tipo</th>
                                <th class="text-left font-medium pb-2 px-3">Descrição</th>
                                <th class="text-right font-medium pb-2 px-3">Valor</th>
                                <th class="text-right font-medium pb-2 px-3 pr-4">Data</th>
                            </tr>
                        </thead>
                        <tbody class="text-ncs-900 dark:text-ncs-50 divide-y divide-ncs-900/20 dark:divide-ncs-50/20">
    `;

  if (lancamentos.length > 0) {
    lancamentos.forEach((l) => {
      const badgeClass =
        l.tipo === 'RECEITA' || l.tipo_registro === 'RECEITA'
          ? 'bg-emerald-100 dark:bg-emerald-900/50 text-emerald-800 dark:text-emerald-200 border-emerald-300 dark:border-emerald-700'
          : 'bg-rose-100 dark:bg-rose-900/50 text-rose-800 dark:text-rose-200 border-rose-300 dark:border-rose-700';
      const valorClass =
        l.tipo === 'RECEITA' || l.tipo_registro === 'RECEITA'
          ? 'text-emerald-600 dark:text-emerald-500'
          : 'text-rose-600 dark:text-rose-500';
      html += `                        <tr class="hover:bg-ncs-50/80 dark:hover:bg-ncs-900/50 transition-colors">
                            <td class="py-3 px-3">
                                <span class="px-2 py-1 text-xs font-medium rounded-md border ${badgeClass}">${l.tipo || l.tipo_registro || 'N/A'}</span>
                            </td>
                            <td class="font-medium text-ncs-900 dark:text-ncs-50 py-3 px-3">${l.descricao || '-'}</td>
                            <td class="text-right font-semibold py-3 px-3 ${valorClass}">R$ ${parseFloat(l.valor || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</td>
                            <td class="text-right text-ncs-900/70 dark:text-ncs-50/70 py-3 px-3 pr-4">${l.data || new Date().toLocaleDateString('pt-BR')}</td>
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
    </div>`;

  return html;
}

function salvarLancamento() {
  const tipo = document.getElementById('tipoRegistro').value;
  const valor = document.getElementById('valorRegistro').value;
  const descricao = document.getElementById('descricaoRegistro').value;
  const data = document.getElementById('dataRegistro').value;
  console.log('Novo lançamento:', { tipo, valor, descricao, data });
  alert('Recurso de lançamento em desenvolvimento - integrar com API');
}

// Exportação de funções para o SPA
window.renderFinanceiroTab = renderFinanceiroTab;
window.salvarLancamento = salvarLancamento;
