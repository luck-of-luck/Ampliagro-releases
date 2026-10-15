'use strict';

function renderPecuariaTab(data) {
  const animais = data && data.animais ? data.animais : [];
  const producoes_leite = data && data.producoes_leite ? data.producoes_leite : [];
  const roi_valor = data && data.roi_valor !== undefined ? data.roi_valor : '0%';
  const custos_valor = data && data.custos_valor !== undefined ? data.custos_valor : 'R$ 0,00';
  const alertas_valor = data && data.alertas_valor !== undefined ? data.alertas_valor : 0;
  const manutencoes_valor =
    data && data.manutencoes_valor !== undefined ? data.manutencoes_valor : 0;

  let html = `<div class="px-6 py-5 space-y-5 bg-ncs-50 dark:bg-ncs-900 min-h-screen text-ncs-900 dark:text-ncs-50">

        <!-- Cabeçalho Tático Integrado - Bento Grid Style -->
        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
            <div class="flex items-center gap-3 mb-2">
                <span class="px-3 py-1.5 text-xs font-medium rounded-md bg-emerald-100 dark:bg-emerald-900/50 text-emerald-800 dark:text-emerald-200"><i class="bi bi-heart-pulse"></i> Módulo Pecuária</span>
            </div>
            <h3 class="text-xl font-bold text-ncs-900 dark:text-ncs-50 mb-1 font-mono">Pecuária e Lactação</h3>
            <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium"><i class="bi bi-egg-fried text-emerald-600 dark:text-emerald-500"></i> Rebanho individual e produção diária de leite</small>
        </div>

        <!-- Analytics Cards - Bento Grid 4 Colunas (mesmo estilo do Dashboard Core) -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider block font-mono">ROI Mensal</span>
                <h3 class="text-xl font-bold text-emerald-600 dark:text-emerald-500 my-1 font-mono">${roi_valor}</h3>
                <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium block font-mono">Retorno sobre investimento</small>
            </div>
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider block font-mono">Custos Operacionais</span>
                <h3 class="text-xl font-bold text-cyan-600 dark:text-cyan-500 my-1 font-mono">${custos_valor}</h3>
                <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium block font-mono">30 dias</small>
            </div>
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider block font-mono">Alertas Ativos</span>
                <h3 class="text-xl font-bold text-amber-600 dark:text-amber-500 my-1 font-mono">${alertas_valor}</h3>
                <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium block font-mono">Requer ação imediata</small>
            </div>
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider block font-mono">Manutenções</span>
                <h3 class="text-xl font-bold text-ncs-900/70 dark:text-ncs-50/70 my-1 font-mono">${manutencoes_valor}</h3>
                <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium block font-mono">Agendadas no período</small>
            </div>
        </div>

        <!-- Sub-grid simétrico: 2 colunas (Formulários + Tabelas) -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <!-- Coluna Esquerda: Dois Formulários em sub-grid vertical -->
            <div class="space-y-4">
                <!-- Formulário 1: Registrar Animal -->
                <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
                    <h5 class="text-lg font-bold text-ncs-900 dark:text-ncs-50 mb-4 font-mono">Registrar Animal</h5>
                    <form method="post" class="space-y-4">
                        <input type="hidden" name="acao" value="animal">
                        <div>
                            <label class="text-sm font-medium text-ncs-900 dark:text-ncs-50 mb-1.5 block font-mono">Identificador do Brinco:</label>
                            <input type="text" name="identificador_brinco" class="w-full rounded-md border border-ncs-900/30 dark:border-ncs-50/30 bg-ncs-50 dark:bg-ncs-900 px-3 py-2 text-ncs-900 dark:text-ncs-50 focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-all" placeholder="Ex: BR-001" required>
                        </div>
                        <div>
                            <label class="text-sm font-medium text-ncs-900 dark:text-ncs-50 mb-1.5 block font-mono">Raça / Genética:</label>
                            <input type="text" name="raca" class="w-full rounded-md border border-ncs-900/30 dark:border-ncs-50/30 bg-ncs-50 dark:bg-ncs-900 px-3 py-2 text-ncs-900 dark:text-ncs-50 focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-all" placeholder="Ex: Nelore" required>
                        </div>
                        <div>
                            <label class="text-sm font-medium text-ncs-900 dark:text-ncs-50 mb-1.5 block font-mono">Categoria:</label>
                            <select name="categoria" class="w-full rounded-md border border-ncs-900/30 dark:border-ncs-50/30 bg-ncs-50 dark:bg-ncs-900 px-3 py-2 text-ncs-900 dark:text-ncs-50 focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-all">
                                <option value="BEZERRA">Bezerro</option>
                                <option value="BEBECA">Bezerra</option>
                                <option value="NOVILHA">Novilha</option>
                                <option value="BOI">Boi</option>
                                <option value="VACA">Vaca</option>
                                <option value="TOURO">Touro</option>
                            </select>
                        </div>
                        <div>
                            <label class="text-sm font-medium text-ncs-900 dark:text-ncs-50 mb-1.5 block font-mono">Status:</label>
                            <select name="status" class="w-full rounded-md border border-ncs-900/30 dark:border-ncs-50/30 bg-ncs-50 dark:bg-ncs-900 px-3 py-2 text-ncs-900 dark:text-ncs-50 focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-all">
                                <option value="ATIVO">Ativo</option>
                                <option value="VACINACAO">Vacinação</option>
                                <option value="SECAGEM">Secagem</option>
                                <option value="INATIVO">Inativo</option>
                            </select>
                        </div>
                        <div>
                            <label class="text-sm font-medium text-ncs-900 dark:text-ncs-50 mb-1.5 block font-mono">Peso (kg):</label>
                            <input type="number" step="0.1" name="peso_inicial" class="w-full rounded-md border border-ncs-900/30 dark:border-ncs-50/30 bg-ncs-50 dark:bg-ncs-900 px-3 py-2 text-ncs-900 dark:text-ncs-50 focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-all" placeholder="Ex: 250.5">
                        </div>
                        <button type="submit" class="w-full rounded-md border border-ncs-900/30 dark:border-ncs-50/30 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-4 py-2 transition-all select-none">Salvar animal</button>
                    </form>
                </div>

                <!-- Formulário 2: Produção de Leite -->
                <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
                    <h5 class="text-lg font-bold text-ncs-900 dark:text-ncs-50 mb-4 font-mono">Produção de Leite</h5>
                    <form method="post" class="space-y-4">
                        <input type="hidden" name="acao" value="leite">
                        <div>
                            <label class="text-sm font-medium text-ncs-900 dark:text-ncs-50 mb-1.5 block font-mono">Data:</label>
                            <input type="date" name="data_coleta" class="w-full rounded-md border border-ncs-900/30 dark:border-ncs-50/30 bg-ncs-50 dark:bg-ncs-900 px-3 py-2 text-ncs-900 dark:text-ncs-50 focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-all" required>
                        </div>
                        <div>
                            <label class="text-sm font-medium text-ncs-900 dark:text-ncs-50 mb-1.5 block font-mono">Litros:</label>
                            <input type="number" step="0.01" name="quantidade_litros" class="w-full rounded-md border border-ncs-900/30 dark:border-ncs-50/30 bg-ncs-50 dark:bg-ncs-900 px-3 py-2 text-ncs-900 dark:text-ncs-50 focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-all" placeholder="Ex: 150.50" required>
                        </div>
                        <button type="submit" class="w-full rounded-md border border-ncs-900/30 dark:border-ncs-50/30 bg-cyan-600 hover:bg-cyan-700 text-white text-xs font-semibold px-4 py-2 transition-all select-none">Registrar coleta</button>
                    </form>
                </div>
            </div>

            <!-- Coluna Direita: Tabelas em Bento Grid -->
            <div class="space-y-4">
                <!-- Tabela 1: Inventário de Rebanho -->
                <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
                    <div class="flex items-center justify-between mb-4">
                        <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider font-mono"><i class="bi bi-clipboard-data"></i> Inventário de Rebanho Ativo</span>
                        <span class="px-2.5 py-1 text-xs font-medium rounded-md bg-ncs-50/80 dark:bg-ncs-900/50 text-ncs-900 dark:text-ncs-50 border border-ncs-900/20 dark:border-ncs-900/30 font-mono">${animais.length || 0} registros</span>
                    </div>
                    <div class="max-h-[280px] overflow-y-auto">
                        <table class="w-full text-sm">
                            <thead class="border-b border-ncs-900/20 dark:border-ncs-50/20">
                                <tr class="text-ncs-900/70 dark:text-ncs-50/70 font-mono text-xs uppercase">
                                    <th class="text-left font-medium pb-2 px-3">Brinco</th>
                                    <th class="text-left font-medium pb-2 px-3">Raça</th>
                                    <th class="text-left font-medium pb-2 px-3">Categoria</th>
                                    <th class="text-left font-medium pb-2 px-3">Status</th>
                                    <th class="text-right font-medium pb-2 px-3">Peso</th>
                                </tr>
                            </thead>
                            <tbody class="text-ncs-900 dark:text-ncs-50 divide-y divide-ncs-900/20 dark:divide-ncs-50/20">
    `;

  if (animais.length > 0) {
    animais.forEach((an) => {
      html += `                        <tr class="hover:bg-ncs-50/80 dark:hover:bg-ncs-900/50 transition-colors">
                                <td class="font-semibold text-ncs-900 dark:text-ncs-50 py-3 px-3 font-mono">${an.identificador_brinco || '---'}</td>
                                <td class="py-3 px-3 text-ncs-900 dark:text-ncs-50">${an.raca || '---'}</td>
                                <td class="py-3 px-3 text-ncs-900 dark:text-ncs-50">${an.categoria_display || an.categoria || '---'}</td>
                                <td class="py-3 px-3 text-ncs-900 dark:text-ncs-50">${an.status_display || an.status || '---'}</td>
                                <td class="text-right text-ncs-900 dark:text-ncs-50 py-3 px-3 font-mono">${an.peso_inicial || 0} kg</td>
                            </tr>
        `;
    });
  } else {
    html += `                        <tr>
                                <td colspan="5" class="text-center text-ncs-900/70 dark:text-ncs-50/70 py-8 font-medium font-mono">Nenhum animal cadastrado no momento.</td>
                            </tr>
        `;
  }

  html += `                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Tabela 2: Histórico de Pesagem/Coleta -->
                <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
                    <div class="flex items-center justify-between mb-4">
                        <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider font-mono"><i class="bi bi-clock-history"></i> Histórico de Pesagem/Coleta</span>
                        <span class="px-2.5 py-1 text-xs font-medium rounded-md bg-ncs-50/80 dark:bg-ncs-900/50 text-ncs-900 dark:text-ncs-50 border border-ncs-900/20 dark:border-ncs-900/30 font-mono">${producoes_leite.length || 0} registros</span>
                    </div>
                    <div class="max-h-[280px] overflow-y-auto">
                        <table class="w-full text-sm">
                            <thead class="border-b border-ncs-900/20 dark:border-ncs-50/20">
                                <tr class="text-ncs-900/70 dark:text-ncs-50/70 font-mono text-xs uppercase">
                                    <th class="text-left font-medium pb-2 px-3">Data</th>
                                    <th class="text-right font-medium pb-2 px-3">Litros</th>
                                    <th class="text-left font-medium pb-2 px-3">Animal</th>
                                </tr>
                            </thead>
                            <tbody class="text-ncs-900 dark:text-ncs-50 divide-y divide-ncs-900/20 dark:divide-ncs-50/20">
    `;

  if (producoes_leite.length > 0) {
    producoes_leite.forEach((p, idx) => {
      const animal = animais && animais[idx] ? animais[idx].identificador_brinco : '---';
      html += `                        <tr class="hover:bg-ncs-50/80 dark:hover:bg-ncs-900/50 transition-colors">
                                <td class="py-3 px-3 text-ncs-900 dark:text-ncs-50 font-mono">${p.data_coleta || '---'}</td>
                                <td class="text-right text-cyan-600 dark:text-cyan-500 font-semibold py-3 px-3 font-mono">${p.quantidade_litros || 0} L</td>
                                <td class="py-3 px-3 font-mono text-ncs-900 dark:text-ncs-50">${animal}</td>
                            </tr>
        `;
    });
  } else {
    html += `                        <tr>
                                <td colspan="3" class="text-center text-ncs-900/70 dark:text-ncs-50/70 py-8 font-medium font-mono">Sem registros de lactação no momento.</td>
                            </tr>
        `;
  }

  html += `                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>`;

  return html;
}
