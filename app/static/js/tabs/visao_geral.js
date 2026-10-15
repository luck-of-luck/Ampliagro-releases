'use strict';

function renderVisaoGeralTab(data) {
  const propriedade = data && data.propriedade ? data.propriedade : { nome_fazenda: '' };
  const funcionarios = data && data.funcionarios ? data.funcionarios : [];
  const maquinarios = data && data.maquinarios ? data.maquinarios : [];
  const commodities = data && data.commodities ? data.commodities : [];
  const receita_graos = data && data.receita_graos !== undefined ? data.receita_graos : 0.0;
  const receita_mel = data && data.receita_mel !== undefined ? data.receita_mel : 0.0;
  const total_receitas = data && data.total_receitas !== undefined ? data.total_receitas : 0.0;
  const total_folha = data && data.total_folha !== undefined ? data.total_folha : 0.0;
  const total_suprimentos =
    data && data.total_suprimentos !== undefined ? data.total_suprimentos : 0.0;
  const total_despesas = data && data.total_despesas !== undefined ? data.total_despesas : 0.0;
  const lucro_liquido = data && data.lucro_liquido !== undefined ? data.lucro_liquido : 0.0;
  const func_em_campo = data && data.func_em_campo !== undefined ? data.func_em_campo : 0;
  const func_manutencao = data && data.func_manutencao !== undefined ? data.func_manutencao : 0;
  const func_parado = data && data.func_parado !== undefined ? data.func_parado : 0;
  const maq_operando = data && data.maq_operando !== undefined ? data.maq_operando : 0;
  const maq_manutencao = data && data.maq_manutencao !== undefined ? data.maq_manutencao : 0;
  const maq_parado = data && data.maq_parado !== undefined ? data.maq_parado : 0;

  let html = `
<div class="px-6 py-5 space-y-5 bg-ncs-50 dark:bg-ncs-900 min-h-screen text-ncs-900 dark:text-ncs-50">
    
    <!-- Hero Header - Bento Card -->
    <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
        <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-4">
            <div>
                <div class="flex items-center gap-3 mb-2">
                    <span class="px-3 py-1.5 text-xs font-medium rounded-md bg-emerald-100 dark:bg-emerald-900/50 text-emerald-800 dark:text-emerald-200"><i class="bi bi-eye-fill"></i> Visão integrada</span>
                </div>
                <h3 class="text-xl font-bold text-ncs-900 dark:text-ncs-50 mb-1">Visão Geral de Gestão Integrada</h3>
                <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium"><i class="bi bi-geo-alt-fill text-emerald-600 dark:text-emerald-500"></i> ${propriedade.nome_fazenda || 'Sem propriedade cadastrada'}</small>
            </div>
        </div>
    </div>

    <!-- Grid principal: Ativos + Commodities -->
    <div class="grid grid-cols-1 xl:grid-cols-3 gap-5 mb-5">
        
        <!-- Seção de Ativos -->
        <div class="xl:col-span-2 space-y-4">
            <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-colors duration-200">
                <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase block mb-4"><i class="bi bi-person-gear"></i> Mão de Obra Ativa</span>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-56 overflow-y-auto pr-1 -mr-1">
    `;

  if (funcionarios.length > 0) {
    funcionarios.forEach((f) => {
      html += `                    <div class="border border-ncs-900/20 dark:border-ncs-50/20/80 rounded-md p-3 transition-all duration-150">
                        <div class="flex items-start justify-between gap-2">
                            <div>
                                <span class="font-semibold text-ncs-900 dark:text-ncs-50 text-sm block">${f.nome || 'Não informado'}</span>
                                <span class="text-xs text-ncs-900/50 dark:text-ncs-900/50">${f.cargo_nome || f.cargo || 'Não informado'}</span>
                            </div>
                            <span class="px-2 py-0.5 text-xs font-medium rounded-md bg-ncs-50/80 dark:bg-ncs-900/80 text-ncs-900 dark:text-ncs-50">Ativo</span>
                        </div>
                        <div class="mt-2 pt-2 border-t border-ncs-900/20 dark:border-ncs-50/20/80">
                            <span class="text-xs text-ncs-900/50 dark:text-ncs-900/50 block mb-1">EPIs: ${f.epis && f.epis.length > 0 ? f.epis.join(', ') : 'N/A'}</span>
                        </div>
                    </div>
        `;
    });
  } else {
    html += `                    <div class="col-span-2 text-center text-ncs-900/50 dark:text-ncs-900/50 py-4 font-medium">Nenhum funcionário ativo.</div>
        `;
  }

  html += `                </div>
            </div>
        </div>
        
        <!-- Seção de Commodities -->
        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-colors duration-200">
            <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase block mb-4"><i class="bi bi-graph-up-arrow"></i> Commodities do Mercado</span>
            <div class="space-y-2 max-h-56 overflow-y-auto pr-1 -mr-1">
    `;

  if (commodities.length > 0) {
    commodities.forEach((item) => {
      html += `                    <div class="flex items-center justify-between py-2 border-b border-ncs-900/20 dark:border-ncs-50/20/80 last:border-0">
                        <span class="font-medium text-ncs-900 dark:text-ncs-50 text-sm">${item.nome}</span>
                        <span class="text-emerald-600 dark:text-emerald-400 font-semibold text-sm">${item.valor || '-'}</span>
                    </div>
        `;
    });
  } else {
    html += `                    <div class="text-center text-ncs-900/50 dark:text-ncs-900/50 py-4 font-medium">Nenhuma commodity disponível.</div>
        `;
  }

  html += `                </div>
        </div>
    </div>

    <!-- Grid de KPIs Financeiros -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-4 shadow-none transition-colors duration-200">
            <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase block">Receita com Grãos</span>
            <h4 class="text-lg font-bold text-emerald-600 dark:text-emerald-500 my-1">R$ ${parseFloat(receita_graos).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</h4>
        </div>
        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-4 shadow-none transition-colors duration-200">
            <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase block">Receita com Mel</span>
            <h4 class="text-lg font-bold text-emerald-600 dark:text-emerald-500 my-1">R$ ${parseFloat(receita_mel).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</h4>
        </div>
        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-4 shadow-none transition-colors duration-200">
            <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase block">Total de Receitas</span>
            <h4 class="text-lg font-bold text-emerald-600 dark:text-emerald-500 my-1">R$ ${parseFloat(total_receitas).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</h4>
        </div>
        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-4 shadow-none transition-colors duration-200">
            <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase block">Lucro Líquido</span>
            <h4 class="text-lg font-bold ${lucro_liquido >= 0 ? 'text-emerald-600 dark:text-emerald-500' : 'text-red-600 dark:text-red-400'} my-1">R$ ${parseFloat(lucro_liquido).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</h4>
        </div>
    </div>

    <!-- Grid de KPIs Operacionais -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-4 shadow-none transition-colors duration-200">
            <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase block mb-2">Funcionários em Campo</span>
            <div class="flex items-center gap-3">
                <span class="text-2xl font-bold text-ncs-900 dark:text-ncs-50">${func_em_campo}</span>
                <span class="text-xs text-ncs-900/70 dark:text-ncs-50/70">ativos | ${func_manutencao} manutenção | ${func_parado} parado</span>
            </div>
        </div>
        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-4 shadow-none transition-colors duration-200">
            <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase block mb-2">Maquinários Operando</span>
            <div class="flex items-center gap-3">
                <span class="text-2xl font-bold text-ncs-900 dark:text-ncs-50">${maq_operando}</span>
                <span class="text-xs text-ncs-900/70 dark:text-ncs-50/70">ativos | ${maq_manutencao} manutenção | ${maq_parado} parado</span>
            </div>
        </div>
        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-4 shadow-none transition-colors duration-200">
            <span class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 uppercase block mb-2">Custos Operacionais</span>
            <div class="flex items-center gap-3">
                <span class="text-2xl font-bold text-red-600 dark:text-red-400">R$ ${(total_despesas + total_folha + total_suprimentos).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</span>
            </div>
        </div>
    </div>
</div>
    `;

  return html;
}
