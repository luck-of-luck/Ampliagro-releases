'use strict';

/**
 * Ausente desenha "—", e nao 0 nem "R$ 0".
 *
 * O `? 0` que estava aqui fabricava um numero: a API nao devolve
 * `total_vendas` nem `clientes_ativos`, entao o fallback produzia zero
 * para TODOS os produtores, sempre. O cabecalho mostrava "R$ 0" de
 * receita a quem tinha receita, e "0 clientes" a quem nao tem como ter —
 * porque nao existe modelo de cliente no projecto.
 *
 * Zero e' uma medicao. "Nao medido" e' outra coisa, e precisa de outro
 * desenho.
 */
const numero = (v, fmt) =>
  v === null || v === undefined || Number.isNaN(v) ? '—' : fmt ? fmt(v) : String(v);

function renderVendasTab(data) {
  const items = data && data.items ? data.items : [];
  const total_vendas = data && data.total_vendas !== undefined ? data.total_vendas : null;
  const clientes_ativos = data && data.clientes_ativos !== undefined ? data.clientes_ativos : null;
  const comissao_total = data && data.comissao_total !== undefined ? data.comissao_total : 0;

  let html = `<div class="px-6 py-5 space-y-5 bg-ncs-50 dark:bg-ncs-900 min-h-screen text-ncs-900 dark:text-ncs-50">

        <!-- Cabeçalho Tático Integrado - Bento Grid Style -->
        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
            <div class="flex items-center gap-3 mb-2">
                <span class="px-3 py-1.5 text-xs font-medium rounded-md bg-emerald-100 dark:bg-emerald-900/50 text-emerald-800 dark:text-emerald-200"><i class="bi bi-cash-stack"></i> Módulo Comercial</span>
            </div>
            <h3 class="text-xl font-bold text-ncs-900 dark:text-ncs-50 mb-1 font-mono">Registro de Vendas Agrícolas</h3>
            <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium"><i class="bi bi-shield-check text-emerald-600 dark:text-emerald-500"></i> Histórico de transações e clientes</small>
        </div>

        <!-- Displays de Métricas - Bento Grid 3 Colunas -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider block font-mono">Total de Vendas</span>
                <h3 class="text-xl font-bold text-emerald-600 dark:text-emerald-500 my-1 font-mono">R$ ${numero(
                  total_vendas,
                  (v) => v.toLocaleString('pt-BR', { minimumFractionDigits: 2 })
                )}</h3>
                <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium block font-mono">Receita bruta acumulada</small>
            </div>
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider block font-mono">Clientes Ativos</span>
                <h3 class="text-xl font-bold text-cyan-600 dark:text-cyan-500 my-1 font-mono">${numero(
                  clientes_ativos
                )}</h3>
                <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium block font-mono">Parceiros comerciais</small>
            </div>
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider block font-mono">Comissão Total</span>
                <h3 class="text-xl font-bold text-amber-600 dark:text-amber-500 my-1 font-mono">R$ ${comissao_total.toLocaleString(
                  'pt-BR',
                  { minimumFractionDigits: 2 }
                )}</h3>
                <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium block font-mono">Taxa sobre vendas</small>
            </div>
        </div>

        <!-- Tabela de Vendas - Bento Grid Style -->
        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
            <div class="flex items-center justify-between mb-4">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider font-mono"><i class="bi bi-clipboard-data"></i> Histórico de Transações</span>
                <span class="px-2.5 py-1 text-xs font-medium rounded-md bg-ncs-50/80 dark:bg-ncs-900/50 text-ncs-900 dark:text-ncs-50 border border-ncs-900/20 dark:border-ncs-900/30 font-mono">${
                  items.length || 0
                } registros</span>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-sm">
                    <thead class="border-b border-ncs-900/20 dark:border-ncs-50/20">
                        <tr class="text-ncs-900/70 dark:text-ncs-50/70 font-mono text-xs uppercase">
                            <th class="text-left font-medium pb-2 px-3">Produto</th>
                            <th class="font-medium pb-2 px-3">Quantidade</th>
                            <th class="font-medium pb-2 px-3">Cliente</th>
                            <th class="font-medium pb-2 px-3">Data</th>
                            <th class="text-right font-medium pb-2 px-3">Valor Total</th>
                        </tr>
                    </thead>
                    <tbody class="text-ncs-900 dark:text-ncs-50 divide-y divide-ncs-900/20 dark:divide-ncs-50/20">
    `;

  if (items.length > 0) {
    items.forEach((item) => {
      html += `                    <tr class="hover:bg-ncs-50/80 dark:hover:bg-ncs-900/50 transition-colors">
                        <td class="font-semibold text-ncs-900 dark:text-ncs-50 py-3 px-3 font-mono">${
                          item.produto || 'Não informado'
                        }</td>
                        <td class="text-center py-3 px-3 text-ncs-900 dark:text-ncs-50 font-mono">${
                          item.quantidade || 0
                        }</td>
                        <td class="py-3 px-3 text-ncs-900 dark:text-ncs-50 font-mono">${
                          item.cliente || 'Não informado'
                        }</td>
                        <td class="py-3 px-3 text-ncs-900 dark:text-ncs-50 font-mono">${
                          item.data || 'N/D'
                        }</td>
                        <td class="text-right text-emerald-600 dark:text-emerald-500 font-semibold py-3 px-3 font-mono">R$ ${parseFloat(
                          item.valor || 0
                        ).toFixed(2)}</td>
                    </tr>
        `;
    });
  } else {
    html += `                    <tr>
                        <td colspan="5" class="text-center text-ncs-900/70 dark:text-ncs-50/70 py-8 font-medium font-mono">Nenhum registro localizado no momento.</td>
                    </tr>
        `;
  }

  html += `                    </tbody>
                </table>
            </div>
        </div>
    </div>`;

  return html;
}
