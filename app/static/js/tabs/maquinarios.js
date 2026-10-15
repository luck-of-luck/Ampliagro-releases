'use strict';

function renderMaquinariosTab(data) {
  const maquinas = data && data.maquinas ? data.maquinas : [];
  const mensagens = data && data.mensagens ? data.mensagens : null;
  const totalMaquinas = maquinas.length || 0;
  const emCampo = 0;
  const precisaRevisao = 0;

  let html = `<div class="px-6 py-5 space-y-5 bg-ncs-50 dark:bg-ncs-900 min-h-screen text-ncs-900 dark:text-ncs-50">

        <!-- Cabeçalho Tático Integrado - Bento Grid Style -->
        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
            <div class="flex items-center gap-3 mb-2">
                <span class="px-3 py-1.5 text-xs font-medium rounded-md bg-emerald-100 dark:bg-emerald-900/50 text-emerald-800 dark:text-emerald-200"><i class="bi bi-cpu-fill"></i> Módulo de Telemetria</span>
            </div>
            <h3 class="text-xl font-bold text-ncs-900 dark:text-ncs-50 mb-1 font-mono">Rastreamento de Frotas e Telemetria Operacional</h3>
            <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium"><i class="bi bi-shield-check text-emerald-600 dark:text-emerald-500"></i> Monitoramento de Tratores, Colhedoras e Implementos Agrícolas</small>
        </div>

        <!-- Displays de Métricas - Bento Grid 3 Colunas -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider block font-mono">Frota Registrada</span>
                <h3 class="text-xl font-bold text-ncs-900 dark:text-ncs-50 my-1 font-mono">${totalMaquinas} máquinas</h3>
                <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium block font-mono">Patrimônio mecânico total</small>
            </div>
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider block font-mono">Disponibilidade Operacional</span>
                <h3 class="text-xl font-bold text-emerald-600 dark:text-emerald-500 my-1 font-mono">${emCampo} máquinas</h3>
                <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium block font-mono">Prontas para operações de campo</small>
            </div>
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider block font-mono">Alertas de Oficina</span>
                <h3 class="text-xl font-bold text-ncs-900/70 dark:text-ncs-50/70 my-1 font-mono">${precisaRevisao} equipamentos</h3>
                <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium block font-mono">Próximos do limite de horímetro</small>
            </div>
        </div>

        <!-- Tabela de controle patrimonial - Bento Grid Style -->
        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
            <div class="flex items-center justify-between mb-4">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider font-mono"><i class="bi bi-list-columns-reverse"></i> Controle Patrimonial Geral</span>
            </div>
            <div class="overflow-x-auto max-h-[500px]">
                <table class="w-full text-sm">
                    <thead class="border-b border-ncs-900/20 dark:border-ncs-50/20">
                        <tr class="text-ncs-900/70 dark:text-ncs-50/70 font-mono text-xs uppercase">
                            <th class="text-left font-medium pb-2 px-3">Modelo / Tipo de Ativo</th>
                            <th class="font-medium pb-2 px-3">Placa / Chassi</th>
                            <th class="font-medium pb-2 px-3">Horímetro Atual</th>
                            <th class="font-medium pb-2 px-3">Status Técnico</th>
                            <th class="font-medium pb-2 px-3 pr-4">Ações</th>
                        </tr>
                    </thead>
                    <tbody class="text-ncs-900 dark:text-ncs-50 divide-y divide-ncs-900/20 dark:divide-ncs-50/20">
    `;

  if (maquinas.length > 0) {
    maquinas.forEach((m) => {
      html += `                        <tr class="hover:bg-ncs-50/80 dark:hover:bg-ncs-900/50 transition-colors">
                            <td class="font-semibold text-ncs-900 dark:text-ncs-50 py-3 px-3 text-left font-mono">
                                <strong><i class="bi bi-truck-flatbed text-emerald-600 dark:text-emerald-500"></i> ${m.tipo || 'Não informado'}</strong>
                            </td>
                            <td class="py-3 px-3 font-mono"><code class="bg-ncs-50/80 dark:bg-ncs-900/50 px-1.5 py-0.5 rounded">${m.placa_chassi || 'Não informado'}</code></td>
                            <td class="py-3 px-3 text-ncs-900 dark:text-ncs-50 font-mono">${m.horimetro || 0} h</td>
                            <td class="py-3 px-3">
                                <span class="px-2 py-0.5 text-xs font-medium rounded-md border border-ncs-900/30 dark:border-ncs-50/30 bg-ncs-50/80 dark:bg-ncs-900/80 text-ncs-900 dark:text-ncs-50">Regular</span>
                            </td>
                            <td class="py-3 px-3 pr-4 text-right">
                                <form method="post" action="." onsubmit="return confirm('Deseja realmente dar baixa e remover este equipamento do sistema?');" class="inline">
                                    <input type="hidden" name="acao" value="excluir_maquina">
                                    <input type="hidden" name="id_maquina" value="${m.id || ''}">
                                    <button type="submit" class="px-3 py-1.5 text-xs font-medium rounded-md border border-red-300 dark:border-red-700 bg-ncs-50 dark:bg-ncs-900 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 transition-all duration-150">Remover</button>
                                </form>
                            </td>
                        </tr>
            `;
    });
  } else {
    html += `                        <tr>
                            <td colspan="5" class="text-center text-ncs-900/70 dark:text-ncs-50/70 py-8 font-medium font-mono">Nenhum trator, colhedora ou implemento mecânico indexado nesta propriedade.</td>
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
