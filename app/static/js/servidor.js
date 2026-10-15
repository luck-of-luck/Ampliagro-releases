/**
 * servidor.js — script que modifica o dashboard servidor de acordo com a área
 * e permissões definidas pelo produtor.
 *
 * Fluxo: produtor cadastra mecânico com área=MECANICA via cadastro-funcionario
 *  -> PerfilUsuario.area_servidor=MECANICA, permissoes={paginas:[...]}
 *  -> servidor loga com nome_fazenda + credenciais -> /servidor/
 *  -> este script busca /api/servidor/config/ e mostra só seções permitidas
 *
 * Cada card no template tem data-pagina e data-area. O script filtra.
 * Pode ser estendido pelo produtor sem mexer no template: só alterar permissoes JSON.
 */
(function () {
  async function loadConfig() {
    try {
      const r = await fetch('/api/servidor/config/', {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });
      if (!r.ok) return null;
      return await r.json();
    } catch (e) {
      return null;
    }
  }

  function applyConfig(data) {
    if (!data || !data.config) return;
    const cfg = data.config;
    const paginas = new Set(cfg.paginas || []);
    const area = data.area || '';
    // Mostra/esconde cards
    document.querySelectorAll('[data-pagina]').forEach((card) => {
      const pag = card.getAttribute('data-pagina');
      const areas = (card.getAttribute('data-area') || '')
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
      // Se paginas contém o card, mostra; se areas contém a área do servidor, mostra também
      const porPagina = paginas.has(pag);
      const porArea = areas.length === 0 || areas.includes(area) || areas.includes('GERAL');
      // Regra: precisa estar na lista de paginas permitidas
      const visivel = porPagina;
      if (visivel) card.classList.remove('js-hidden');
      else card.classList.add('js-hidden');
    });

    // Desabilita botões de criar/editar se não tem permissão
    if (!cfg.pode_criar) {
      document.querySelectorAll('.servidor-card .pcrud-btn-primary').forEach((b) => {
        b.disabled = true;
        b.title = 'Criação desabilitada pelo produtor';
        b.style.opacity = '0.5';
      });
    }
    if (!cfg.pode_editar) {
      document
        .querySelectorAll('[data-editable]')
        .forEach((el) => el.setAttribute('readonly', 'true'));
    }

    // Atualiza badge de permissão se existir
    const flag = document.getElementById('permFlag');
    if (flag) {
      flag.textContent =
        (cfg.pode_criar ? 'criar ' : '') + (cfg.pode_editar ? 'editar' : 'somente leitura');
    }
    const pagesEl = document.getElementById('permPages');
    if (pagesEl) pagesEl.textContent = (cfg.paginas || []).join(', ');

    console.log('[servidor.js] área', area, 'paginas', [...paginas], 'config', cfg);
  }

  document.addEventListener('DOMContentLoaded', async () => {
    const data = await loadConfig();
    if (data) applyConfig(data);
    else console.warn('[servidor.js] sem config — usando render server-side');
  });

  // Expose para debug / para o produtor testar permissões no console
  window.ServidorJS = { loadConfig, applyConfig };
})();
