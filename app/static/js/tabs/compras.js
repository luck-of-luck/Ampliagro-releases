'use strict';

function renderComprasTab(data) {
  const solicitacoes = data && data.solicitacoes ? data.solicitacoes : [];

  let html = `<div class="px-6 py-5 space-y-5 bg-ncs-50 dark:bg-ncs-900 min-h-screen text-ncs-900 dark:text-ncs-50">

        <!-- Hero Header - Bento Card -->
        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
            <div class="flex items-center gap-3 mb-2">
                <span class="px-3 py-1.5 text-xs font-medium rounded-md bg-emerald-100 dark:bg-emerald-900/50 text-emerald-800 dark:text-emerald-200"><i class="bi bi-cart-plus-fill"></i> Compras</span>
            </div>
            <h3 class="text-xl font-bold text-ncs-900 dark:text-ncs-50 mb-1 font-mono">Registro de Compras e Solicitações</h3>
            <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium"><i class="bi bi-shield-check text-emerald-600 dark:text-emerald-500"></i> Histórico de pedidos e fornecedores</small>
        </div>

        <!-- Tabela de Compras - Bento Grid Style -->
        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
            <div class="flex items-center justify-between mb-4">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider font-mono"><i class="bi bi-clipboard-data"></i> Histórico de Solicitações</span>
                <span class="px-2.5 py-1 text-xs font-medium rounded-md bg-ncs-50/80 dark:bg-ncs-900/50 text-ncs-900 dark:text-ncs-50 border border-ncs-900/20 dark:border-ncs-900/30 font-mono">${solicitacoes.length || 0} registros</span>
            </div>
            <div class="overflow-x-auto max-h-[500px]">
                <table class="w-full text-sm">
                    <thead class="border-b border-ncs-900/20 dark:border-ncs-50/20">
                        <tr class="text-ncs-900/70 dark:text-ncs-50/70 font-mono text-xs uppercase">
                            <th class="text-left font-medium pb-2 px-3">Insumo</th>
                            <th class="font-medium pb-2 px-3">Quantidade</th>
                            <th class="font-medium pb-2 px-3">Solicitante</th>
                            <th class="font-medium pb-2 px-3">Status</th>
                            <th class="text-right font-medium pb-2 px-3 pr-4">Data</th>
                        </tr>
                    </thead>
                    <tbody class="text-ncs-900 dark:text-ncs-50 divide-y divide-ncs-900/20 dark:divide-ncs-50/20">
    `;

  if (solicitacoes.length > 0) {
    solicitacoes.forEach((s) => {
      html += `                        <tr class="hover:bg-ncs-50/80 dark:hover:bg-ncs-900/50 transition-colors">
                            <td class="font-semibold text-ncs-900 dark:text-ncs-50 py-3 px-3 text-left font-mono">${s.insumo_nome || 'Não informado'}</td>
                            <td class="py-3 px-3 text-ncs-900 dark:text-ncs-50 font-mono">${s.quantidade || 0}</td>
                            <td class="py-3 px-3 text-ncs-900 dark:text-ncs-50 font-mono">${s.solicitante || 'Não informado'}</td>
                            <td class="py-3 px-3">
                                <span class="px-2 py-0.5 text-xs font-medium rounded-md bg-cyan-100 dark:bg-cyan-900/50 text-cyan-800 dark:text-cyan-200 border border-cyan-300 dark:border-cyan-700 font-mono">${s.status || 'N/D'}</span>
                            </td>
                            <td class="text-right text-ncs-900/70 dark:text-ncs-50/70 py-3 px-3 pr-4 font-mono">${s.data || 'N/D'}</td>
                        </tr>
            `;
    });
  } else {
    html += `                        <tr>
                            <td colspan="5" class="text-center text-ncs-900/70 dark:text-ncs-50/70 py-8 font-medium font-mono">Nenhum registro localizado no momento.</td>
                        </tr>
            `;
  }

  html += `                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        // Scripts iniciais
    </script>
    `;

  return html;
}
