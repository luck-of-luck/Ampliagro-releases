'use strict';

function renderNovidadesTab(data) {
  const total_alertas = data && data.total_alertas !== undefined ? data.total_alertas : 0;
  const alertas_estoque = data && data.alertas_estoque ? data.alertas_estoque : [];
  const alertas_maquinas = data && data.alertas_maquinas ? data.alertas_maquinas : [];
  const laudos_pendentes = data && data.laudos_pendentes ? data.laudos_pendentes : [];

  let html = `<div class="px-6 py-5 space-y-5 bg-ncs-50 dark:bg-ncs-900 min-h-screen text-ncs-900 dark:text-ncs-50">

        <!-- Hero Header - Bento Card -->
        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
            <div class="flex items-center justify-between mb-2">
                <div class="flex items-center gap-3">
                    <span class="px-3 py-1.5 text-xs font-medium rounded-md bg-amber-100 dark:bg-amber-900/50 text-amber-800 dark:text-amber-200"><i class="bi bi-bell-fill"></i> Notificações</span>
                </div>
                <span class="px-3 py-1.5 text-xs font-bold rounded-md bg-amber-600 dark:bg-amber-700 text-white">${total_alertas} ALERTAS ATIVOS</span>
            </div>
            <h3 class="text-xl font-bold text-ncs-900 dark:text-ncs-50 mb-1 font-mono">Central de Novidades e Alertas</h3>
            <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium"><i class="bi bi-shield-check text-emerald-600 dark:text-emerald-500"></i> Monitoramento de eventos críticos e notificações do sistema</small>
        </div>

        <!-- Alertas de estoque -->
        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200 mb-4">
            <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider block mb-4 font-mono"><i class="bi bi-box-seam"></i> Alertas de Estoque</span>
            <div class="overflow-x-auto max-h-[200px]">
                <table class="w-full text-sm">
                    <thead class="border-b border-ncs-900/20 dark:border-ncs-50/20">
                        <tr class="text-ncs-900/70 dark:text-ncs-50/70 font-mono text-xs uppercase">
                            <th class="text-left font-medium pb-2 px-3">Produto</th>
                            <th class="font-medium pb-2 px-3">Lote</th>
                            <th class="font-medium pb-2 px-3">Marca</th>
                            <th class="text-right font-medium pb-2 px-3 pr-4">Quantidade</th>
                        </tr>
                    </thead>
                    <tbody class="text-ncs-900 dark:text-ncs-50 divide-y divide-ncs-900/20 dark:divide-ncs-50/20">
    `;

  if (alertas_estoque.length > 0) {
    alertas_estoque.forEach((a) => {
      html += `                        <tr class="hover:bg-ncs-50/80 dark:hover:bg-ncs-900/50 transition-colors">
                            <td class="font-semibold text-ncs-900 dark:text-ncs-50 py-3 px-3 text-left font-mono">${a.nome || 'N/D'}</td>
                            <td class="py-3 px-3 font-mono"><code class="bg-ncs-50/80 dark:bg-ncs-900/50 px-1.5 py-0.5 rounded">${a.lote || 'N/D'}</code></td>
                            <td class="py-3 px-3 text-ncs-900 dark:text-ncs-50 font-mono">${a.marca || 'N/D'}</td>
                            <td class="text-right text-red-600 dark:text-red-400 font-semibold py-3 px-3 pr-4 font-mono">${a.quantidade_estoque || 0}</td>
                        </tr>
            `;
    });
  } else {
    html += `                        <tr>
                            <td colspan="4" class="text-center text-ncs-900/70 dark:text-ncs-50/70 py-3 font-medium font-mono">Nenhum alerta de estoque ativo.</td>
                        </tr>
            `;
  }

  html += `                    </tbody>
                </table>
            </div>
        </div>

        <!-- Alertas de máquinas -->
        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200 mb-4">
            <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider block mb-4 font-mono"><i class="bi bi-tools"></i> Alertas de Máquinas</span>
            <div class="overflow-x-auto max-h-[200px]">
                <table class="w-full text-sm">
                    <thead class="border-b border-ncs-900/20 dark:border-ncs-50/20">
                        <tr class="text-ncs-900/70 dark:text-ncs-50/70 font-mono text-xs uppercase">
                            <th class="text-left font-medium pb-2 px-3">Equipamento</th>
                            <th class="font-medium pb-2 px-3">Placa/Chassi</th>
                            <th class="font-medium pb-2 px-3">Última Manutenção</th>
                            <th class="text-right font-medium pb-2 px-3 pr-4">Horímetro</th>
                        </tr>
                    </thead>
                    <tbody class="text-ncs-900 dark:text-ncs-50 divide-y divide-ncs-900/20 dark:divide-ncs-50/20">
    `;

  if (alertas_maquinas.length > 0) {
    alertas_maquinas.forEach((m) => {
      html += `                        <tr class="hover:bg-ncs-50/80 dark:hover:bg-ncs-900/50 transition-colors">
                            <td class="font-semibold text-ncs-900 dark:text-ncs-50 py-3 px-3 text-left font-mono">${m.tipo || 'N/D'}</td>
                            <td class="py-3 px-3 font-mono"><code class="bg-ncs-50/80 dark:bg-ncs-900/50 px-1.5 py-0.5 rounded">${m.placa_chassi || 'N/D'}</code></td>
                            <td class="py-3 px-3 text-ncs-900 dark:text-ncs-50 font-mono">${m.ultima_manutencao || 'N/D'}</td>
                            <td class="text-right text-ncs-900 dark:text-ncs-50 py-3 px-3 pr-4 font-mono">${m.horimetro || 0}h</td>
                        </tr>
            `;
    });
  } else {
    html += `                        <tr>
                            <td colspan="4" class="text-center text-ncs-900/70 dark:text-ncs-50/70 py-3 font-medium font-mono">Nenhum alerta de máquina ativo.</td>
                        </tr>
            `;
  }

  html += `                    </tbody>
                </table>
            </div>
        </div>

        <!-- Laudos pendentes -->
        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
            <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider block mb-4 font-mono"><i class="bi bi-journal-medical"></i> Laudos Pendentes</span>
            <div class="overflow-x-auto max-h-[200px]">
                <table class="w-full text-sm">
                    <thead class="border-b border-ncs-900/20 dark:border-ncs-50/20">
                        <tr class="text-ncs-900/70 dark:text-ncs-50/70 font-mono text-xs uppercase">
                            <th class="text-left font-medium pb-2 px-3">Talhão</th>
                            <th class="text-right font-medium pb-2 px-3 pr-4">Data da Coleta</th>
                        </tr>
                    </thead>
                    <tbody class="text-ncs-900 dark:text-ncs-50 divide-y divide-ncs-900/20 dark:divide-ncs-50/20">
    `;

  if (laudos_pendentes.length > 0) {
    laudos_pendentes.forEach((l) => {
      html += `                        <tr class="hover:bg-ncs-50/80 dark:hover:bg-ncs-900/50 transition-colors">
                            <td class="font-semibold text-ncs-900 dark:text-ncs-50 py-3 px-3 text-left font-mono">${l.talhao || 'N/D'}</td>
                            <td class="text-right text-ncs-900 dark:text-ncs-50 py-3 px-3 pr-4 font-mono">${l.data_coleta || 'N/D'}</td>
                        </tr>
            `;
    });
  } else {
    html += `                        <tr>
                            <td colspan="2" class="text-center text-ncs-900/70 dark:text-ncs-50/70 py-3 font-medium font-mono">Nenhum laudo pendente.</td>
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
