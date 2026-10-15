/**
 * Ampliagro Campo Mode - 60-second guided onboarding
 * Animated, interactive, gets user to first "wow" in < 60s
 */
class CampoMode {
  constructor() {
    this.step = 0;
    this.totalSteps = 6;
    this.startTime = null;
    this.userData = {};
    this.demoData = {
      fazenda: {
        nome: 'Fazenda Modelo',
        area: 1240,
        uf: 'MT',
        cidade: 'Primavera do Leste',
        bioma: 'cerrado',
      },
      cultura: { nome: 'Soja', variedade: 'Intacta RR2 PRO', area: 420, safra: '2024/25' },
      talhoes: [
        { nome: 'Talhão A', cultura: 'Soja', area: 180, variedade: 'Intacta', estagio: 'Floração' },
        {
          nome: 'Talhão B',
          cultura: 'Milho',
          area: 120,
          variedade: 'Dekalb 390',
          estagio: 'Vegetativo',
        },
      ],
      servidores: [
        { nome: 'Carlos Mecânico', cargo: 'MECANICA', user: 'carlos.mec' },
        { nome: 'Ana Campo', cargo: 'CAMPO', user: 'ana.campo' },
      ],
    };
    this.currentStep = 0;
    this.container = null;
  }

  async start() {
    // Check if already onboarded
    if (localStorage.getItem('ampliagro_onboarded') === 'true') return;

    this.startTime = Date.now();
    this.render();
    this.bindEvents();
    document.body.classList.add('campo-mode-active');
  }

  render() {
    const steps = [
      {
        id: 'welcome',
        title: 'Bem-vindo ao Ampliagro',
        subtitle: 'Sistema completo de gestão agrícola em 60 segundos',
        icon: 'bi bi-seedling',
        cta: 'Começar',
        action: () => this.nextStep(),
      },
      {
        id: 'fazenda',
        title: 'Sua Fazenda',
        subtitle: 'Cadastre a propriedade base',
        icon: 'bi bi-house-fill',
        cta: 'Criar Fazenda',
        form: [
          {
            key: 'nome',
            label: 'Nome da Fazenda',
            type: 'text',
            placeholder: 'Ex: Fazenda Modelo',
            required: true,
          },
          {
            key: 'area',
            label: 'Área Total (ha)',
            type: 'number',
            step: '0.1',
            placeholder: '1240',
            required: true,
          },
          {
            key: 'uf',
            label: 'Estado (UF)',
            type: 'select',
            options: [
              'AC',
              'AL',
              'AP',
              'AM',
              'BA',
              'CE',
              'DF',
              'ES',
              'GO',
              'MA',
              'MT',
              'MS',
              'MG',
              'PA',
              'PB',
              'PR',
              'PE',
              'PI',
              'RJ',
              'RN',
              'RS',
              'RO',
              'RR',
              'SC',
              'SP',
              'SE',
              'TO',
            ],
            required: true,
          },
          { key: 'cidade', label: 'Cidade', type: 'text', placeholder: 'Primavera do Leste' },
          {
            key: 'bioma',
            label: 'Bioma',
            type: 'select',
            options: ['amazonia', 'cerrado', 'mata_atlantica', 'caatinga', 'pampa', 'pantanal'],
          },
        ],
      },
      {
        id: 'cultura',
        title: 'Primeira Cultura',
        subtitle: 'Cadastre a cultura principal da safra',
        icon: 'bi bi-tree-fill',
        cta: 'Adicionar Cultura',
        form: [
          {
            key: 'cultura',
            label: 'Cultura',
            type: 'select',
            options: [
              'Soja',
              'Milho',
              'Algodão',
              'Café',
              'Cana',
              'Trigo',
              'Arroz',
              'Feijão',
              'Sorgo',
              'Outro',
            ],
            required: true,
          },
          { key: 'variedade', label: 'Variedade', type: 'text', placeholder: 'Intacta RR2 PRO' },
          { key: 'area', label: 'Área (ha)', type: 'number', step: '0.1', placeholder: '420' },
          { key: 'safra', label: 'Safra', type: 'text', placeholder: '2024/25' },
          { key: 'plantio', label: 'Data Plantio', type: 'date' },
        ],
      },
      {
        id: 'talhoes',
        title: 'Talhões',
        subtitle: 'Divida a área em talhões para gestão precisa',
        icon: 'bi bi-geo-alt-fill',
        cta: 'Criar Talhões Demo',
        action: () => this.createDemoTalhoes(),
      },
      {
        id: 'equipe',
        title: 'Sua Equipe',
        subtitle: 'Cadastre os servidores que vão operar no sistema',
        icon: 'bi bi-people-fill',
        cta: 'Criar Servidores Demo',
        action: () => this.createDemoServidores(),
      },
      {
        id: 'complete',
        title: '🎉 Pronto em 60s!',
        subtitle: 'Sua fazenda está configurada. Vamos começar?',
        icon: 'bi bi-check-circle-fill',
        cta: 'Entrar no Sistema',
        action: () => this.complete(),
      },
    ];

    this.steps = steps;
    this.render();
  }

  render() {
    const step = this.steps[this.currentStep];
    const elapsed = ((Date.now() - this.startTime) / 1000).toFixed(1);
    const progress = (this.currentStep / (this.steps.length - 1)) * 100;

    document.body.innerHTML = `
      <div class="campo-mode-overlay">
        <div class="campo-modal">
          <!-- Progress -->
          <div class="campo-progress">
            <div class="campo-progress-bar" style="width:${progress}%"></div>
            <div class="campo-progress-text">${this.currentStep + 1} de ${this.steps.length} • ${elapsed}s</div>
          </div>

          <div class="campo-content">
            <div class="campo-icon"><i class="${step.icon}"></i></div>
            <h1 class="campo-title">${step.title}</h1>
            <p class="campo-subtitle">${step.subtitle}</p>

            ${step.form ? this.renderForm(step.form) : ''}
            ${step.action && !step.form ? `<p style="color:var(--cor-texto-medio);font-size:.9rem;margin:1rem 0">${step.subtitle}</p>` : ''}

            <div class="campo-actions">
              ${this.currentStep > 0 ? `<button class="campo-btn campo-btn-secondary" onclick="window.CampoMode.prevStep()"><i class="bi bi-chevron-left"></i> Voltar</button>` : ''}
              <button class="campo-btn campo-btn-primary" onclick="window.CampoMode.${step.action || 'nextStep'}()">
                <i class="bi bi-${step.action === 'complete' ? 'check2' : 'chevron-right'}"></i> ${step.cta}
              </button>
            </div>

            ${
              step.demoData
                ? `
              <div class="campo-demo-hint">
                <i class="bi bi-lightning-charge"></i> Modo Demo: ${step.demoData}
              </div>
            `
                : ''
            }
          </div>

          <div class="campo-timer" id="campoTimer">${Math.round((Date.now() - this.startTime) / 1000)}s</div>
        </div>
      </div>
    `;

    // Add styles
    this.injectStyles();
  }

  injectStyles() {
    if (document.getElementById('campo-mode-styles')) return;
    const style = document.createElement('style');
    style.id = 'campo-mode-styles';
    style.textContent = `
      .campo-mode-overlay{position:fixed;inset:0;background:rgba(15,23,42,.95);backdrop-filter:blur(8px);z-index:99999;display:flex;align-items:center;justify-content:center;padding:1rem;font-family:'Inter',system-ui,sans-serif}
      .campo-modal{background:#fff;border-radius:20px;max-width:520px;width:100%;max-height:90vh;overflow:hidden;box-shadow:0 25px 50px -12px rgba(0,0,0,.25);animation:campoIn .4s cubic-bezier(.22,.8,.25,1)}
      @keyframes campoIn{from{opacity:0;transform:translateY(20px) scale(.96)}to{opacity:1;transform:none}}
      .campo-progress{height:4px;background:var(--s200);border-radius:2px;overflow:hidden;margin:0 1.5rem 1rem}
      .campo-progress-bar{height:100%;background:linear-gradient(90deg,var(--cor-primaria),var(--cor-primaria-clara));transition:width .3s ease}
      .campo-progress-text{font-size:.7rem;color:var(--cor-texto-medio);text-align:right;padding:0 1.5rem .5rem;font-family:var(--f-mono)}
      .campo-content{padding:1.5rem 1.5rem 1rem;text-align:center}
      .campo-icon{width:72px;height:72px;border-radius:16px;background:linear-gradient(135deg,var(--cor-primaria),var(--cor-primaria-clara));display:flex;align-items:center;justify-content:center;font-size:28px;color:#fff;margin:0 auto 1rem;box-shadow:0 10px 30px rgba(15,157,110,.3)}
      .campo-title{font-family:var(--f-display);font-weight:800;font-size:1.5rem;color:var(--cor-texto);margin:0 0 .5rem}
      .campo-subtitle{color:var(--cor-texto-medio);font-size:.95rem;line-height:1.5;margin:0 0 1.5rem}
      .campo-form{display:flex;flex-direction:column;gap:1rem;text-align:left;margin:1rem 0}
      .campo-field{display:flex;flex-direction:column;gap:.4rem}
      .campo-field label{font-size:.75rem;font-weight:600;color:var(--cor-texto);text-transform:uppercase;letter-spacing:.03em}
      .campo-field input,.campo-field select{padding:.7rem 1rem;border:1.5px solid var(--cor-borda);border-radius:10px;font-size:.95rem;font-family:inherit;transition:border .15s,box-shadow .15s}
      .campo-field input:focus,.campo-field select:focus{outline:none;border-color:var(--cor-primaria);box-shadow:0 0 0 3px rgba(15,157,110,.15)}
      .campo-field input::placeholder{color:var(--cor-texto-fraco)}
      .campo-actions{display:flex;gap:.75rem;margin-top:1.5rem;padding-top:1rem;border-top:1px solid var(--cor-borda)}
      .campo-btn{flex:1;padding:.85rem 1rem;border-radius:10px;font-weight:700;font-size:.9rem;display:flex;align-items:center;justify-content:center;gap:.5rem;cursor:pointer;transition:all .15s;border:none}
      .campo-btn-primary{background:linear-gradient(135deg,var(--cor-primaria),var(--cor-primaria-clara));color:#fff}
      .campo-btn-primary:hover{transform:translateY(-2px);box-shadow:0 8px 20px rgba(15,157,110,.3)}
      .campo-btn-secondary{background:var(--s100);color:var(--cor-texto);border:1px solid var(--cor-borda)}
      .campo-btn-secondary:hover{background:var(--s200)}
      .campo-demo-hint{margin-top:1rem;padding:.75rem;background:linear-gradient(135deg,#fff7ed,#fef3c7);border:1px dashed #f59e0b;border-radius:8px;font-size:.78rem;color:#92400e;display:flex;align-items:center;gap:.5rem}
      .campo-timer{position:absolute;bottom:.75rem;right:1rem;font-family:var(--f-mono);font-size:.75rem;color:var(--cor-texto-medio);background:rgba(0,0,0,.05);padding:.3rem .7rem;border-radius:999px}
      .campo-form .campo-field:has(input[type="date"]){position:relative}
      .campo-form .campo-field:has(input[type="date"])::after{content:attr(data-placeholder);position:absolute;right:1rem;top:50%;transform:translateY(-50%);color:var(--cor-texto-fraco);font-size:.85rem;pointer-events:none}
    `;
    document.head.appendChild(style);
  }

  bindEvents() {
    window.CampoMode = {
      nextStep: () => this.nextStep(),
      prevStep: () => this.prevStep(),
      createDemoTalhoes: () => this.createDemoTalhoes(),
      createDemoServidores: () => this.createDemoServidores(),
      complete: () => this.complete(),
    };
  }

  async nextStep() {
    // Collect form data if exists
    if (this.steps[this.currentStep].form) {
      const formData = new FormData(document.querySelector('.campo-form'));
      this.userData[this.steps[this.currentStep].id] = Object.fromEntries(formData);
    } else if (this.steps[this.currentStep].action) {
      await this.steps[this.currentStep].action();
    }

    if (this.currentStep < this.steps.length - 1) {
      this.currentStep++;
      this.render();
    }
  }

  prevStep() {
    if (this.currentStep > 0) {
      this.currentStep--;
      this.render();
    }
  }

  async createDemoTalhoes() {
    // Create demo talhoes
    this.showToast('Talhões demo criados!');
    await new Promise((r) => setTimeout(r, 500));
    this.nextStep();
  }

  async createDemoServidores() {
    this.showToast('Servidores demo criados: Carlos (Mecânica) e Ana (Campo)!');
    await new Promise((r) => setTimeout(r, 500));
    this.nextStep();
  }

  complete() {
    // Save user data
    localStorage.setItem('ampliagro_onboarded', 'true');
    localStorage.setItem('ampliagro_userdata', JSON.stringify(this.userData));
    localStorage.setItem('ampliagro_onboard_time', Date.now().toString());

    this.showToast('🎉 Onboarding concluído! Bem-vindo ao Ampliagro!');
    document.body.classList.remove('campo-mode-active');
    document.body.innerHTML = ''; // Will be replaced by main app

    // Redirect to dashboard
    setTimeout(() => (window.location.href = '/'), 1500);
  }

  showToast(msg, type = 'success') {
    const existing = document.getElementById('campoToast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.id = 'campoToast';
    toast.style.cssText = `
      position:fixed;bottom:20px;right:20px;z-index:100000;
      background:${type === 'error' ? '#dc2626' : type === 'warning' ? '#b45309' : '#0f9d6e'};
      color:#fff;padding:1rem 1.5rem;border-radius:10px;
      box-shadow:0 10px 30px rgba(0,0,0,.2);font-weight:600;
      animation:slideIn .3s ease;
    `;
    toast.textContent = msg;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
  }
}

// Auto-start if not onboarded
document.addEventListener('DOMContentLoaded', () => {
  if (!localStorage.getItem('ampliagro_onboarded')) {
    window.CampoMode = new CampoMode();
    window.CampoMode.start();
  }
});

// Export
if (typeof module !== 'undefined') module.exports = CampoMode;
