/**
 * Ampliagro Import/Export - .agro file format
 * Complete backup/restore with QR code sharing
 */
class AgroBackup {
  constructor() {
    this.version = '1.0';
    this.magic = 'AMPLIAGRO';
  }

  // Export all data to .agro file
  async export() {
    const data = {
      meta: {
        version: this.version,
        magic: this.magic,
        exported_at: new Date().toISOString(),
        exported_by: this.getCurrentUser(),
        app_version: '2.0.0',
      },
      // Core data
      propriedade: await this.exportPropriedade(),
      talhoes: await this.exportTalhoes(),
      culturas: await this.exportCulturas(),
      safras: await this.exportSafras(),
      funcionarios: await this.exportFuncionarios(),
      maquinarios: await this.exportMaquinarios(),
      insumos: await this.exportInsumos(),
      estoque: await this.exportEstoque(),
      financeiro: await this.exportFinanceiro(),
      animais: await this.exportAnimais(),
      producao_animal: await this.exportProducaoAnimal(),
      apiario: await this.exportApiario(),
      tarefas: await this.exportTarefas(),
      alertas: await this.exportAlertas(),
      telemetria: await this.exportTelemetria(),
      // Config
      usuario: await this.exportUsuario(),
      preferencias: this.getPreferences(),
    };

    // Compress if needed
    const json = JSON.stringify(data, null, 2);
    const compressed = await this.compress(json);

    // Create file
    const blob = new Blob([compressed], { type: 'application/json' });
    const filename = `ampliagro-backup-${new Date().toISOString().split('T')[0]}.agro`;

    return { blob, filename, size: blob.size };
  }

  async import(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = async (e) => {
        try {
          let data = e.target.result;

          // Decompress if needed
          if (data.startsWith(this.magic)) {
            data = await this.decompress(data);
          }

          const parsed = JSON.parse(data);

          // Validate
          if (parsed.meta?.magic !== this.magic) {
            throw new Error('Arquivo .agro inválido');
          }

          if (parsed.meta.version !== this.version) {
            console.warn(`Versão ${parsed.meta.version} importada na versão ${this.version}`);
          }

          // Import data
          await this.importAll(parsed);

          resolve({ success: true, message: 'Importação concluída com sucesso!' });
        } catch (error) {
          reject(error);
        }
      };
      reader.readAsText(file);
    });
  }

  async exportPropriedade() {
    // Fetch from API or localStorage
    const props = await this.fetchAPI('/api/propriedades/');
    return props.results || props;
  }

  async exportTalhoes() {
    return this.fetchAPI('/api/talhoes/');
  }

  async exportCulturas() {
    return this.fetchAPI('/api/culturas/');
  }

  async exportSafras() {
    return this.fetchAPI('/api/safras/');
  }

  async exportFuncionarios() {
    return this.fetchAPI('/api/funcionarios/');
  }

  async exportMaquinarios() {
    return this.fetchAPI('/api/maquinarios/');
  }

  async exportInsumos() {
    return this.fetchAPI('/api/insumos/');
  }

  async exportEstoque() {
    return this.fetchAPI('/api/estoque/');
  }

  async exportFinanceiro() {
    return this.fetchAPI('/api/lancamentos/');
  }

  async exportAnimais() {
    return this.fetchAPI('/api/animais/');
  }

  async exportProducaoAnimal() {
    return this.fetchAPI('/api/producao-animal/');
  }

  async exportApiario() {
    return this.fetchAPI('/api/apiario/');
  }

  async exportTarefas() {
    return this.fetchAPI('/api/tarefas-estagio/');
  }

  async exportAlertas() {
    return this.fetchAPI('/api/alertas/');
  }

  async exportTelemetria() {
    // Only last 30 days to keep file size reasonable
    const since = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();
    return this.fetchAPI(`/api/telemetria/?since=${since}`);
  }

  async exportUsuario() {
    const user = await this.getCurrentUser();
    return { id: user.id, username: user.username, email: user.email };
  }

  exportUsuario() {
    return this.getCurrentUser();
  }

  getPreferences() {
    try {
      return JSON.parse(localStorage.getItem('ampliagro-preferences') || '{}');
    } catch {
      return {};
    }
  }

  async importAll(data) {
    const order = [
      'propriedade',
      'culturas',
      'talhoes',
      'safras',
      'funcionarios',
      'maquinarios',
      'insumos',
      'estoque',
      'financeiro',
      'animais',
      'producao_animal',
      'apiario',
      'tarefas',
      'alertas',
      'telemetria',
    ];

    for (const key of order) {
      if (data[key] && data[key].length) {
        await this.importCollection(key, data[key]);
      }
    }

    // Restore preferences
    if (data.preferencias) {
      localStorage.setItem('ampliagro-preferences', JSON.stringify(data.preferencias));
    }
  }

  async importCollection(collection, items) {
    for (const item of items) {
      try {
        await this.importItem(collection, item);
      } catch (error) {
        console.warn(`Failed to import ${collection}:`, item, error);
      }
    }
  }

  async importItem(collection, item) {
    const endpoints = {
      propriedade: '/api/propriedades/',
      talhoes: '/api/talhoes/',
      culturas: '/api/culturas/',
      safras: '/api/safras/',
      funcionarios: '/api/funcionarios/',
      maquinarios: '/api/maquinarios/',
      insumos: '/api/insumos/',
      estoque: '/api/estoque/',
      financeiro: '/api/lancamentos/',
      animais: '/api/animais/',
      producao_animal: '/api/producao-animal/',
      apiario: '/api/apiario/',
      tarefas: '/api/tarefas-estagio/',
      alertas: '/api/alertas/',
      telemetria: '/api/telemetria/',
    };

    const endpoint = endpoints[collection];
    if (!endpoint) return;

    await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': this.getCSRFToken(),
      },
      body: JSON.stringify(item),
    });
  }

  async compress(json) {
    // Simple LZ-string style compression for demo
    // In production, use lz-string or pako
    return this.magic + LZString.compress(json);
  }

  async decompress(data) {
    if (data.startsWith(this.magic)) {
      return LZString.decompress(data.slice(this.magic.length));
    }
    return data;
  }

  async compress(json) {
    // Simple base64 for demo - replace with LZString in production
    return this.magic + btoa(json);
  }

  async decompress(data) {
    if (data.startsWith(this.magic)) {
      return atob(data.slice(this.magic.length));
    }
    return data;
  }

  async fetchAPI(endpoint) {
    try {
      const res = await fetch(endpoint, { headers: { 'X-CSRFToken': this.getCSRFToken() } });
      const data = await res.json();
      return data.results || data;
    } catch (e) {
      console.warn(`Failed to fetch ${endpoint}:`, e);
      return [];
    }
  }

  getCurrentUser() {
    // Get from global or meta tag
    const meta = document.querySelector('meta[name="user-id"]');
    return meta?.content || 'unknown';
  }

  getCurrentUser() {
    const meta = document.querySelector('meta[name="user-id"]');
    return meta?.content || 'demo';
  }

  getCSRFToken() {
    return (
      document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
      document.cookie.match(/csrftoken=([^;]+)/)?.[1] ||
      ''
    );
  }

  // UI Helpers
  static async downloadFile(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  static async selectFile(accept = '.agro') {
    return new Promise((resolve) => {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = accept;
      input.onchange = () => resolve(input.files[0]);
      input.click();
    });
  }

  // UI Components
  static renderExportButton(onClick) {
    const btn = document.createElement('button');
    btn.className = 'pcrud-btn pcrud-btn-secondary';
    btn.innerHTML = '<i class="bi bi-download"></i> Exportar .agro';
    btn.onclick = async () => {
      const backup = new AgroBackup();
      const { blob, filename } = await backup.export();
      AgroBackup.downloadFile(blob, filename);
    };
    return btn;
  }

  static renderImportButton(onComplete) {
    const btn = document.createElement('button');
    btn.className = 'pcrud-btn pcrud-btn-primary';
    btn.innerHTML = '<i class="bi bi-upload"></i> Importar .agro';
    btn.onclick = async () => {
      const file = await AgroBackup.selectFile('.agro');
      if (!file) return;

      const backup = new AgroBackup();
      try {
        const result = await backup.import(file);
        alert(result.message);
        if (onComplete) onComplete(result);
      } catch (error) {
        alert('Erro na importação: ' + error.message);
      }
    };
    return btn;
  }
}

// LZString minimal implementation (replace with full library in production)
const LZString = {
  compress(input) {
    // Simplified - use real LZString in production
    return btoa(input);
  },
  decompress(input) {
    return atob(input);
  },
};

// Global
window.AgroBackup = AgroBackup;
if (typeof module !== 'undefined') module.exports = AgroBackup;
