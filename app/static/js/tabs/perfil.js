'use strict';

function renderPerfilTab(data) {
  const usuario = data && data.usuario ? data.usuario : { username: '', email: '' };
  const propriedade =
    data && data.propriedade
      ? data.propriedade
      : { nome_fazenda: '', estado: '', uf: '', cidade: '', extensoes: 0.0, cultura_principal: '' };

  let html = `
<div class="px-6 py-5 space-y-5 bg-ncs-50 dark:bg-ncs-900 min-h-screen text-ncs-900 dark:text-ncs-50">
    
    <!-- Hero Header - Bento Card -->
    <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-all duration-200">
        <div class="flex items-center gap-3 mb-2">
            <span class="px-3 py-1.5 text-xs font-medium rounded-md bg-emerald-100 dark:bg-emerald-900/50 text-emerald-800 dark:text-emerald-200"><i class="bi bi-person-circle"></i> Perfil</span>
        </div>
        <h3 class="text-xl font-bold text-ncs-900 dark:text-ncs-50 mb-1">Perfil da Fazenda</h3>
        <small class="text-xs text-ncs-900/70 dark:text-ncs-50/70 font-medium">Configurações e dados da propriedade</small>
    </div>

    <!-- Grid de cards -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-colors duration-200">
            <h5 class="font-bold text-ncs-900 dark:text-ncs-50 mb-4"><i class="bi bi-person-badge"></i> Dados do Usuário</h5>
            <div class="space-y-3">
                <div>
                    <label class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 block mb-1">Nome de Usuário:</label>
                    <input type="text" readonly value="${usuario.username || ''}" 
                           class="w-full px-3 py-2 bg-ncs-50 dark:bg-ncs-900/50 border border-ncs-900/30 dark:border-ncs-50/30 rounded-md text-ncs-900 dark:text-ncs-50">
                </div>
                <div>
                    <label class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 block mb-1">Email:</label>
                    <input type="email" readonly value="${usuario.email || ''}" 
                           class="w-full px-3 py-2 bg-ncs-50 dark:bg-ncs-900/50 border border-ncs-900/30 dark:border-ncs-50/30 rounded-md text-ncs-900 dark:text-ncs-50">
                </div>
            </div>
        </div>

        <div class="bg-ncs-50 dark:bg-ncs-900 border border-ncs-900/20 dark:border-ncs-50/20 rounded-md p-5 shadow-none transition-colors duration-200">
            <h5 class="font-bold text-ncs-900 dark:text-ncs-50 mb-4"><i class="bi bi-geo-alt"></i> Dados da Propriedade</h5>
            <div class="space-y-3">
                <div>
                    <label class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 block mb-1">Nome da Fazenda:</label>
                    <input type="text" readonly value="${propriedade.nome_fazenda || ''}" 
                           class="w-full px-3 py-2 bg-ncs-50 dark:bg-ncs-900/50 border border-ncs-900/30 dark:border-ncs-50/30 rounded-md text-ncs-900 dark:text-ncs-50">
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 block mb-1">Estado:</label>
                        <input type="text" readonly value="${propriedade.estado || ''} (${propriedade.uf || ''})" 
                               class="w-full px-3 py-2 bg-ncs-50 dark:bg-ncs-900/50 border border-ncs-900/30 dark:border-ncs-50/30 rounded-md text-ncs-900 dark:text-ncs-50">
                    </div>
                    <div>
                        <label class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 block mb-1">Cidade:</label>
                        <input type="text" readonly value="${propriedade.cidade || ''}" 
                               class="w-full px-3 py-2 bg-ncs-50 dark:bg-ncs-900/50 border border-ncs-900/30 dark:border-ncs-50/30 rounded-md text-ncs-900 dark:text-ncs-50">
                    </div>
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 block mb-1">Extensões (Ha):</label>
                        <input type="text" readonly value="${propriedade.extensoes || 0}" 
                               class="w-full px-3 py-2 bg-ncs-50 dark:bg-ncs-900/50 border border-ncs-900/30 dark:border-ncs-50/30 rounded-md text-ncs-900 dark:text-ncs-50">
                    </div>
                    <div>
                        <label class="text-xs font-semibold text-ncs-900/70 dark:text-ncs-50/70 block mb-1">Cultura Principal:</label>
                        <input type="text" readonly value="${propriedade.cultura_principal || ''}" 
                               class="w-full px-3 py-2 bg-ncs-50 dark:bg-ncs-900/50 border border-ncs-900/30 dark:border-ncs-50/30 rounded-md text-ncs-900 dark:text-ncs-50">
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
    `;

  return html;
}
