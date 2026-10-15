'use strict';

function renderGestaoTab(data) {
  const indicadores = data && data.indicadores ? data.indicadores : [];
  const dre_linhas = data && data.dre_linhas ? data.dre_linhas : [];
  const colheitas = data && data.colheitas ? data.colheitas : [];
  const funcionarios = data && data.funcionarios ? data.funcionarios : [];
  const lucroLiquido = 0;

  let html = `<div class="px-6 py-5 space-y-5 bg-ncs-50 dark:bg-ncs-900 min-h-screen text-ncs-900 dark:text-ncs-50">

        <!-- Cabeçalho Tático Integrado - Bento Grid Style -->
        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
            <div class="flex items-center gap-3 mb-2">
                <span class="px-3 py-1.5 text-xs font-medium rounded-md bg-emerald-100 dark:bg-emerald-900/50 text-emerald-800 dark:text-emerald-200"><i class="bi bi-pie-chart-fill"></i> Gestão Estratégica</span>
            </div>
            <h3 class="text-xl font-bold text-ncs-900 dark:text-ncs-50 mb-1 font-mono">Controladoria Geral</h3>
            <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium"><i class="bi bi-shield-check text-emerald-600 dark:text-emerald-500"></i> Indicadores financeiros, custos e resultado operacional consolidados</small>
        </div>

        <!-- Grid de indicadores - Bento Grid 3 Colunas -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider block font-mono">Custo por Saca Produzida</span>
                <h3 class="text-xl font-bold text-ncs-900 dark:text-ncs-50 my-1 font-mono">R$ 0,00</h3>
                <small class="text-xs font-medium block font-mono"><span class="text-emerald-600 dark:text-emerald-500"><i class="bi bi-shield-check"></i> Preço ref: R$ 140,00</span></small>
            </div>
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider block font-mono">Custo por Litro de Leite</span>
                <h3 class="text-xl font-bold text-ncs-900 dark:text-ncs-50 my-1 font-mono">R$ 0,00</h3>
                <small class="text-xs font-medium block font-mono"><span class="text-emerald-600 dark:text-emerald-500"><i class="bi bi-shield-check"></i> Preço ref: R$ 2,45</span></small>
            </div>
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider block font-mono">Resultado Líquido Consolidado</span>
                <h3 class="text-xl font-bold text-emerald-600 dark:text-emerald-500 my-1 font-mono">R$ 0,00</h3>
                <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium block font-mono">Balanço integrado de movimentações</small>
            </div>
        </div>

        <!-- Grid principal: DRE + Gráfico - Bento Grid 2 Colunas -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-5">
            <!-- DRE Table -->
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider block mb-4 font-mono"><i class="bi bi-calculator"></i> Demonstrativo de Resultado Balançado (DRE)</span>
                <div class="overflow-x-auto">
                    <table class="w-full text-sm">
                        <thead class="bg-ncs-50/80 dark:bg-ncs-900/50 uppercase tracking-wider">
                            <tr class="border-b border-ncs-900/20 dark:border-ncs-50/20">
                                <th class="text-left font-medium py-2 px-3 text-xs font-mono">Conta de Controle</th>
                                <th class="text-right font-medium py-2 px-3 text-xs font-mono">Agrícola</th>
                                <th class="text-right font-medium py-2 px-3 text-xs font-mono">Pecuária</th>
                            </tr>
                        </thead>
                        <tbody class="text-ncs-900 dark:text-ncs-50 divide-y divide-ncs-900/20 dark:divide-ncs-50/20">
                `;

  if (dre_linhas.length > 0) {
    dre_linhas.forEach((linha) => {
      const valorClass =
        linha.tipo === 'receita'
          ? 'text-emerald-600 dark:text-emerald-500'
          : linha.tipo === 'despesa'
            ? 'text-rose-600 dark:text-rose-500'
            : 'text-ncs-900 dark:text-ncs-50';
      html += `                        <tr class="hover:bg-ncs-50/80 dark:hover:bg-ncs-900/50 transition-colors">
                                <td class="text-left font-medium py-2 px-3 text-xs text-ncs-900/70 dark:text-ncs-50/70 font-mono">${linha.conta || 'Conta não informada'}</td>
                                <td class="text-right ${valorClass} font-semibold py-2 px-3 text-xs font-mono">R$ ${parseFloat(linha.agricola || 0).toFixed(2)}</td>
                                <td class="text-right ${valorClass} font-semibold py-2 px-3 text-xs font-mono">R$ ${parseFloat(linha.pecuaria || 0).toFixed(2)}</td>
                            </tr>
                `;
    });
  } else {
    html += `                        <tr>
                                <td colspan="3" class="text-center text-ncs-900/70 dark:text-ncs-50/70 py-8 font-medium font-mono">Nenhum dado financeiro registrado no momento.</td>
                            </tr>
                `;
  }

  html += `                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Chart Card -->
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none flex flex-col transition-all duration-200">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider block mb-4 font-mono"><i class="bi bi-graph-up-arrow"></i> Curva de Desembolso Proporcional Real (Safra 2026)</span>
                <div class="h-56 flex-1">
                    <canvas id="chartFluxoProjetadoGeral"></canvas>
                </div>
            </div>
        </div>

        <!-- Grid secundário: Colheitas + Funcionários - Bento Grid 2 Colunas -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <!-- Tabela de Colheitas -->
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider block mb-4 font-mono"><i class="bi bi-box-seam"></i> Histórico de Volumes e Escoamento</span>
                <div class="overflow-x-auto max-h-48">
                    <table class="w-full text-xs">
                        <thead class="bg-ncs-50/80 dark:bg-ncs-900/50 uppercase tracking-wider">
                            <tr class="border-b border-ncs-900/20 dark:border-ncs-50/20">
                                <th class="text-left font-medium py-2 px-3 font-mono">Safra</th>
                                <th class="font-medium py-2 px-3 font-mono">Volume</th>
                                <th class="font-medium py-2 px-3 font-mono">Umidade</th>
                                <th class="font-medium py-2 px-3 font-mono">Status</th>
                            </tr>
                        </thead>
                        <tbody class="text-ncs-900 dark:text-ncs-50 divide-y divide-ncs-900/20 dark:divide-ncs-50/20">
                `;

  if (colheitas.length > 0) {
    colheitas.forEach((c) => {
      html += `                        <tr class="hover:bg-ncs-50/80 dark:hover:bg-ncs-900/50 transition-colors">
                                <td class="text-left font-semibold text-ncs-900 dark:text-ncs-50 py-2 px-3 font-mono">${c.safra_nome || c.nome_safra || 'Safra não identificada'}</td>
                                <td class="text-center py-2 px-3 text-ncs-900 dark:text-ncs-50 font-mono">${c.volume_colhido || 0} sacas</td>
                                <td class="text-center py-2 px-3 text-ncs-900 dark:text-ncs-50 font-mono">${c.umidade || 0}%</td>
                                <td class="text-center py-2 px-3"><span class="px-2 py-0.5 text-xs font-medium rounded-md bg-emerald-100 dark:bg-emerald-900/50 text-emerald-800 dark:text-emerald-200 border border-emerald-300 dark:border-emerald-700 font-mono">Auditado</span></td>
                            </tr>
                `;
    });
  } else {
    html += `                        <tr>
                                <td colspan="4" class="text-center text-ncs-900/70 dark:text-ncs-50/70 py-4 font-medium font-mono">Nenhum volume de colheita registrado no momento.</td>
                            </tr>
                `;
  }

  html += `                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Tabela de Funcionários -->
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase tracking-wider block mb-4 font-mono"><i class="bi bi-people"></i> Alocação Patrimonial de Mão de Obra</span>
                <div class="overflow-x-auto max-h-48">
                    <table class="w-full text-xs">
                        <thead class="bg-ncs-50/80 dark:bg-ncs-900/50 uppercase tracking-wider">
                            <tr class="border-b border-ncs-900/20 dark:border-ncs-50/20">
                                <th class="text-left font-medium py-2 px-3 font-mono">Colaborador</th>
                                <th class="font-medium py-2 px-3 font-mono">Cargo</th>
                                <th class="text-right font-medium py-2 px-3 font-mono">Remuneração</th>
                            </tr>
                        </thead>
                        <tbody class="text-ncs-900 dark:text-ncs-50 divide-y divide-ncs-900/20 dark:divide-ncs-50/20">
                `;

  if (funcionarios.length > 0) {
    funcionarios.forEach((f) => {
      html += `                        <tr class="hover:bg-ncs-50/80 dark:hover:bg-ncs-900/50 transition-colors">
                                <td class="text-left font-semibold text-ncs-900 dark:text-ncs-50 py-2 px-3 font-mono">${f.nome || 'Não informado'}</td>
                                <td class="text-center py-2 px-3"><span class="px-2 py-0.5 text-xs font-medium rounded-md bg-ncs-50/80 dark:bg-ncs-900/80 text-ncs-900 dark:text-ncs-50 border border-ncs-900/20 dark:border-ncs-900/30 font-mono">${f.cargo_nome || f.cargo || 'Não informado'}</span></td>
                                <td class="text-right text-ncs-900 dark:text-ncs-50 font-semibold py-2 px-3 font-mono">R$ ${(f.salario || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</td>
                            </tr>
                `;
    });
  } else {
    html += `                        <tr>
                                <td colspan="3" class="text-center text-ncs-900/70 dark:text-ncs-50/70 py-4 font-medium font-mono">Nenhum funcionário ativo ou folha salarial mapeada nesta propriedade.</td>
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
        document.addEventListener('DOMContentLoaded', function() {
            var ctx = document.getElementById('chartFluxoProjetadoGeral');
            if (ctx && window.Chart) {
                var palAcc = getComputedStyle(document.documentElement).getPropertyValue('--pal-accent').trim() || '#0f9d6e';
                var palFill = getComputedStyle(document.documentElement).getPropertyValue('--pal-accent-fill').trim() || 'rgba(83, 221, 108, 0.15)';
                var palTick = getComputedStyle(document.documentElement).getPropertyValue('--pal-tick').trim() || '#6b5b7a';
                new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: [],
                        datasets: [{
                            label: 'Fluxo Projetado',
                            data: [],
                            borderColor: palAcc,
                            backgroundColor: palFill,
                            fill: true,
                            tension: 0.3,
                            borderWidth: 2,
                            pointRadius: 4,
                            pointHoverRadius: 6
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        font: {
                            size: 12,
                            family: 'Inter, system-ui, sans-serif'
                        },
                        scales: {
                            y: {
                                ticks: {
                                    color: palTick,
                                    font: {
                                        size: 12,
                                        weight: '500',
                                        family: 'Inter, system-ui, sans-serif'
                                    },
                                    padding: 8
                                },
                                grid: { display: false },
                                border: { display: false }
                            },
                            x: {
                                ticks: {
                                    color: palTick,
                                    font: {
                                        size: 12,
                                        weight: '500',
                                        family: 'Inter, system-ui, sans-serif'
                                    },
                                    padding: 8
                                },
                                grid: { display: false },
                                border: { display: false }
                            }
                        },
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                backgroundColor: document.documentElement.classList.contains('dark') ? '#0f172a' : '#ffffff',
                                titleColor: document.documentElement.classList.contains('dark') ? '#f1f5f9' : '#1e293b',
                                bodyColor: document.documentElement.classList.contains('dark') ? '#f1f5f9' : '#1e293b',
                                borderColor: document.documentElement.classList.contains('dark') ? '#334155' : '#cbd5e1',
                                borderWidth: 1,
                                cornerRadius: 8,
                                padding: 12,
                                displayColors: false,
                                callbacks: {
                                    label: function(context) {
                                        return 'Fluxo: R$ ' + (context.raw || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 });
                                    }
                                }
                            }
                        }
                    }
                });
            }
        });
    </script>
    `;

  return html;
}
