'use strict';

function renderArmazemTab(data) {
  const armazens = data && data.armazens ? data.armazens : [];
  const silos_ativos = data && data.silos_ativos !== undefined ? data.silos_ativos : 0;
  const capacidade_total = data && data.capacidade_total !== undefined ? data.capacidade_total : 0;
  const ocupacao_media = data && data.ocupacao_media !== undefined ? data.ocupacao_media : 0;

  let html = `<div class="px-6 py-5 space-y-5 bg-ncs-50 dark:bg-ncs-900 min-h-screen text-ncs-900 dark:text-ncs-50">

        <!-- Cabeçalho Tático Integrado - Bento Grid Style -->
        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
            <div class="flex items-center gap-3 mb-2">
                <span class="px-3 py-1.5 text-xs font-medium rounded-md bg-emerald-100 dark:bg-emerald-900/50 text-emerald-800 dark:text-emerald-200"><i class="bi bi-warehouse"></i> Módulo Armazém</span>
            </div>
            <h3 class="text-xl font-bold text-ncs-900 dark:text-ncs-50 mb-1 font-mono">Gestão de Armazém e Armazenagem</h3>
            <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium"><i class="bi bi-shield-check text-emerald-600 dark:text-emerald-500"></i> Monitoramento de silos e estoques</small>
        </div>

        <!-- Displays de Métricas - Bento Grid 3 Colunas -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider block font-mono">Silos Ativos</span>
                <h3 class="text-xl font-bold text-cyan-600 dark:text-cyan-500 my-1 font-mono">${silos_ativos}</h3>
                <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium block font-mono">Unidades operacionais</small>
            </div>
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider block font-mono">Capacidade Total</span>
                <h3 class="text-xl font-bold text-amber-600 dark:text-amber-500 my-1 font-mono">${capacidade_total} un</h3>
                <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium block font-mono">Volume total armazenado</small>
            </div>
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider block font-mono">Ocupação Média</span>
                <h3 class="text-xl font-bold text-emerald-600 dark:text-emerald-500 my-1 font-mono">${ocupacao_media}%</h3>
                <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium block font-mono">Taxa de uso</small>
            </div>
        </div>

        <!-- Tabela de Silos - Bento Grid Style -->
        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
            <div class="flex items-center justify-between mb-4">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider font-mono"><i class="bi bi-clipboard-data"></i> Registro de Silos</span>
                <span class="px-2.5 py-1 text-xs font-medium rounded-md bg-ncs-50/80 dark:bg-ncs-900/50 text-ncs-900 dark:text-ncs-50 border border-ncs-900/20 dark:border-ncs-900/30 font-mono">${armazens.length || 0} registros</span>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-sm">
                    <thead class="border-b border-ncs-900/20 dark:border-ncs-50/20">
                        <tr class="text-ncs-900/70 dark:text-ncs-50/70 font-mono text-xs uppercase">
                            <th class="text-left font-medium pb-2 px-3">Silo</th>
                            <th class="font-medium pb-2 px-3">Ocupação</th>
                            <th class="font-medium pb-2 px-3">Temperatura</th>
                            <th class="font-medium pb-2 px-3">Ventilação</th>
                            <th class="text-right font-medium pb-2 px-3">Status</th>
                        </tr>
                    </thead>
                    <tbody class="text-ncs-900 dark:text-ncs-50 divide-y divide-ncs-900/20 dark:divide-ncs-50/20">
    `;

  if (armazens.length > 0) {
    armazens.forEach((a) => {
      html += `                    <tr class="hover:bg-ncs-50/80 dark:hover:bg-ncs-900/50 transition-colors">
                        <td class="font-semibold text-ncs-900 dark:text-ncs-50 py-3 px-3 font-mono">Silo #${a.id || '---'}</td>
                        <td class="text-center py-3 px-3 text-ncs-900 dark:text-ncs-50 font-mono">${a.capacidade_ocupada || 0} un</td>
                        <td class="py-3 px-3 text-ncs-900 dark:text-ncs-50 font-mono">${a.temperatura_silo || 0}°C</td>
                        <td class="py-3 px-3 font-mono">
                            ${
                              a.controle_ventilacao || false
                                ? '<span class="px-2 py-0.5 text-xs font-medium rounded-md bg-emerald-100 dark:bg-emerald-900/50 text-emerald-800 dark:text-emerald-200 border border-emerald-300 dark:border-emerald-700">Ativo</span>'
                                : '<span class="px-2 py-0.5 text-xs font-medium rounded-md bg-ncs-50/80 dark:bg-ncs-900/80 text-ncs-900 dark:text-ncs-50 border border-ncs-900/20 dark:border-ncs-900/30">Inativo</span>'
                            }
                        </td>
                        <td class="text-right text-ncs-900/70 dark:text-ncs-50/70 py-3 px-3 font-mono">${a.entrada_saida_graos || 'N/D'}</td>
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
