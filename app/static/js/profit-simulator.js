/**
 * Ampliagro Profit Simulator - Interactive profit calculator
 * Drag sliders to see real-time profit impact
 */
class ProfitSimulator {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.state = {
      // Inputs
      area: 100, // hectares
      produtividade: 60, // sc/ha
      preco_saca: 145, // R$/sc
      custo_ha: 2200, // R$/ha
      custo_fixo: 50000, // R$/safra
      // Calculated
      receita: 0,
      custo_total: 0,
      lucro: 0,
      margem: 0,
      roi: 0,
    };

    this.config = {
      area: { min: 1, max: 50000, step: 1, label: 'Área (ha)', unit: 'ha' },
      produtividade: { min: 10, max: 200, step: 1, label: 'Produtividade', unit: 'sc/ha' },
      preco_saca: { min: 50, max: 300, step: 1, label: 'Preço da Saca', unit: 'R$/sc' },
      custo_ha: { min: 500, max: 5000, step: 50, label: 'Custo/ha', unit: 'R$/ha' },
      custo_fixo: { min: 0, max: 500000, step: 1000, label: 'Custo Fixo', unit: 'R$' },
    };

    this.init();
  }

  init() {
    this.render();
    this.bindEvents();
    this.calculate();
    this.updateUI();
  }

  render() {
    this.container.innerHTML = `
      <div class="profit-simulator" style="font-family: 'Inter', sans-serif;">
        <!-- Header -->
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.5rem;padding-bottom:1rem;border-bottom:1px solid var(--cor-borda)">
          <div>
            <h2 style="font-family:var(--f-display);font-weight:800;font-size:1.5rem;margin:0"><i class="bi bi-cash-stack"></i> Simulador de Lucro</h2>
            <p style="color:var(--cor-texto-medio);font-size:.85rem;margin:.25rem 0 0">Arraste os controles para ver o impacto no lucro em tempo real</p>
          </div>
          <div style="display:flex;gap:.5rem">
            <button class="btn-secondary btn-sm" id="simReset"><i class="bi bi-arrow-counterclockwise"></i> Reset</button>
            <button class="btn-primary btn-sm" id="simExport"><i class="bi bi-download"></i> Exportar CSV</button>
          </div>
        </div>

        <!-- Main Grid -->
        <div style="display:grid;grid-template-columns:1fr 380px;gap:1.5rem">
          <!-- Controls -->
          <div class="simulator-controls" style="display:flex;flex-direction:column;gap:1.5rem">
            ${Object.entries(this.config)
              .map(
                ([key, cfg]) => `
              <div class="sim-control" data-key="${key}">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem">
                  <label style="font-weight:600;font-size:.85rem;color:var(--cor-texto)">${cfg.label}</label>
                  <span class="sim-value" id="val-${key}" style="font-weight:700;color:var(--cor-primaria);font-size:.95rem;background:var(--cor-primaria-suave);padding:.2rem .6rem;border-radius:999px;font-family:var(--f-mono)">${this.state[key]}${cfg.unit}</span>
                </label>
                <input type="range"
                  class="sim-slider"
                  data-key="${key}"
                  min="${cfg.min}" max="${cfg.max}" step="${cfg.step}"
                  value="${this.state[key]}"
                  style="width:100%;accent-color:var(--cor-primaria);cursor:pointer">
                <div style="display:flex;justify-content:space-between;font-size:.7rem;color:var(--cor-texto-fraco);margin-top:.25rem">
                  <span>${cfg.min}${cfg.unit}</span>
                  <span>${cfg.max}${cfg.unit}</span>
                </div>
              </div>
            `
              )
              .join('')}
          </div>

          <!-- Results Panel -->
          <div class="simulator-results" style="background:linear-gradient(135deg,var(--cor-primaria) 0%,#0a7d56 100%);border-radius:16px;padding:1.5rem;color:#fff;position:sticky;top:1.5rem">
            <h3 style="font-family:var(--f-display);font-weight:800;font-size:1.1rem;margin:0 0 1rem;display:flex;align-items:center;gap:.5rem"><i class="bi bi-graph-up"></i> Resultado</h3>

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1.5rem">
              <div class="result-card" style="background:rgba(255,255,255,.15);border-radius:12px;padding:1rem;backdrop-filter:blur(10px)">
                <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;opacity:.8;margin-bottom:.25rem">Receita Total</div>
                <div id="resReceita" style="font:700 1.5rem var(--f-mono)">R$ 0</div>
                <div style="font-size:.7rem;opacity:.7;margin-top:.25rem">Área × Prod. × Preço</div>
              </div>
              <div class="result-card" style="background:rgba(255,255,255,.15);border-radius:12px;padding:1rem;backdrop-filter:blur(10px)">
                <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;opacity:.8;margin-bottom:.25rem">Custo Total</div>
                <div id="resCusto" style="font:700 1.5rem var(--f-mono)">R$ 0</div>
                <div style="font-size:.7rem;opacity:.7;margin-top:.25rem">Fixos + Variáveis</div>
              </div>
            </div>

            <div class="result-card" style="background:rgba(255,255,255,.2);border-radius:12px;padding:1rem;backdrop-filter:blur(10px);margin-bottom:1rem">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem">
                <div>
                  <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;opacity:.8">Lucro Líquido</div>
                  <div id="resLucro" style="font:800 2rem var(--f-mono)">${this.formatCurrency(
                    0
                  )}</div>
                </div>
                <div style="text-align:right">
                  <div style="font-size:.7rem;opacity:.8">Margem</div>
                  <div id="resMargem" style="font:700 1.5rem var(--f-mono);color:#fff">0%</div>
                </div>
              </div>
              <div style="font-size:.7rem;opacity:.7">ROI: <span id="resROI" style="font-weight:700">0%</span></div>
            </div>

            <!-- Break-even -->
            <div style="border-top:1px solid rgba(255,255,255,.2);padding-top:1rem;margin-top:1rem">
              <div style="font-size:.7rem;opacity:.8;margin-bottom:.5rem">Ponto de Equilíbrio</div>
              <div style="display:flex;justify-content:space-between;font-family:var(--f-mono)">
                <span>Produtividade mínima: <span id="beProd" style="font-weight:700">-</span> sc/ha</span>
                <span>Preço mínimo: <span id="bePreco" style="font-weight:700">-</span> R$/sc</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Sensitivity Analysis -->
      <div style="margin-top:1.5rem">
        <h4 style="font:700 1rem var(--f-display);margin:0 0 1rem">Análise de Sensibilidade</h4>
        <div class="sensitivity-grid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem">
          ${[
            { key: 'produtividade', label: 'Variação Produtividade (±20%)' },
            { key: 'preco_saca', label: 'Variação Preço (±20%)' },
            { key: 'custo_ha', label: 'Variação Custo/ha (±20%)' },
          ]
            .map(
              (s) => `
            <div style="background:var(--cor-fundo-card);border:1px solid var(--cor-borda);border-radius:12px;padding:1rem">
              <div style="font-weight:600;font-size:.85rem;margin-bottom:.5rem">${s.label}</div>
              <div style="display:flex;justify-content:space-between;font-family:var(--f-mono);font-size:.9rem">
                <span>-20%: <span id="sens-${s.key}-neg" style="font-weight:700;color:var(--cor-erro)">-</span></span>
                <span>Base: <span id="sens-${s.key}-base" style="font-weight:700;color:var(--cor-primaria)">-</span></span>
                <span>+20%: <span id="sens-${s.key}-pos" style="font-weight:700;color:var(--cor-sucesso)">+</span></span>
              </div>
            </div>
          `
            )
            .join('')}
        </div>
      </div>
    `;
  }

  bindEvents() {
    // Sliders
    this.container.querySelectorAll('.sim-slider').forEach((slider) => {
      slider.addEventListener('input', (e) => {
        const key = e.target.dataset.key;
        const value = parseFloat(e.target.value);
        this.state[key] = value;
        this.calculate();
        this.updateUI();
      });
    });

    // Reset button
    this.container.querySelector('#simReset')?.addEventListener('click', () => {
      this.reset();
    });

    // Export CSV
    this.container.querySelector('#simExport')?.addEventListener('click', () => {
      this.exportCSV();
    });

    // Keyboard support
    document.addEventListener('keydown', (e) => {
      if (e.key === 'r' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        this.reset();
      }
      if (e.key === 'e' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        this.exportCSV();
      }
    });
  }

  calculate() {
    const s = this.state;
    const c = this.config;

    // Receita = Área × Produtividade × Preço
    s.receita = s.area * s.produtividade * s.preco_saca;

    // Custo total = (Área × Custo/ha) + Custo Fixo
    s.custo_total = s.area * s.custo_ha + s.custo_fixo;

    // Lucro
    s.lucro = s.receita - s.custo_total;

    // Margem
    s.margem = s.receita > 0 ? (s.lucro / s.receita) * 100 : 0;

    // ROI
    s.roi = s.custo_total > 0 ? (s.lucro / s.custo_total) * 100 : 0;

    // Break-even
    const custoVariavelHa = this.state.custo_ha;
    const precoSaca = this.state.preco_saca;
    const custoFixoTotal = this.state.custo_fixo;

    // Break-even produtividade: (custo_fixo + area * custo_ha) / (area * preco)
    const beProd = custoFixoTotal / (this.state.area * precoSaca) + custoVariavelHa / precoSaca;

    // Break-even preço: (custo_fixo + area * custo_ha) / (area * produtividade)
    const bePreco =
      (custoFixoTotal + this.state.area * custoVariavelHa) /
      (this.state.area * this.state.produtividade);

    // Sensitivity
    const baseLucro = this.state.lucro;
    const sens = {};
    ['produtividade', 'preco_saca', 'custo_ha'].forEach((key) => {
      const orig = this.state[key];
      this.state[key] = orig * 0.8;
      this.calculate();
      const neg = this.state.lucro;
      this.state[key] = orig * 1.2;
      this.calculate();
      const pos = this.state.lucro;
      this.state[key] = orig;
      this.calculate();
      this.sensitivities[key] = { base: baseLucro, neg, pos };
    });
    this.sensitivities = sens;
  }

  updateUI() {
    const s = this.state;
    const c = this.config;

    // Update sliders and values
    Object.entries(c).forEach(([key, cfg]) => {
      const slider = document.querySelector(`.sim-slider[data-key="${key}"]`);
      const valEl = document.getElementById(`val-${key}`);
      if (slider) slider.value = s[key];
      if (valEl) valEl.textContent = `${this.formatNumber(s[key])}${cfg.unit}`;
    });

    // Results
    const format = (v) => this.formatCurrency(v);
    const pct = (v) => v.toFixed(1) + '%';

    const el = (id) => document.getElementById(id);
    const setEl = (id, val) => {
      const e = el(id);
      if (e) e.textContent = val;
    };
    setEl('resReceita', this.formatCurrency(s.receita));
    setEl('resCusto', this.formatCurrency(s.custo_total));
    setEl('resLucro', this.formatCurrency(s.lucro));
    setEl('resMargem', s.margem.toFixed(1) + '%');
    setEl('resROI', s.roi.toFixed(1) + '%');

    // Break-even
    const beProd =
      this.state.custo_fixo / (this.state.area * this.state.preco_saca) +
      this.state.custo_ha / this.state.preco_saca;
    const bePreco =
      (this.state.custo_fixo + this.state.area * this.state.custo_ha) /
      (this.state.area * this.state.produtividade);
    setEl('beProd', this.formatNumber(beProd.toFixed(1)));
    setEl('bePreco', this.formatCurrency(bePreco));

    // Sensitivity
    if (this.sensitivities) {
      Object.entries(this.sensitivities).forEach(([key, vals]) => {
        setEl(`sens-${key}-neg`, this.formatCurrency(vals.neg));
        setEl(`sens-${key}-base`, this.formatCurrency(vals.base));
        setEl(`sens-${key}-pos`, this.formatCurrency(vals.pos));
      });
    }
  }

  reset() {
    this.state = {
      area: 100,
      produtividade: 60,
      preco_saca: 145,
      custo_ha: 2200,
      custo_fixo: 50000,
      receita: 0,
      custo_total: 0,
      lucro: 0,
      margem: 0,
      roi: 0,
    };
    this.calculate();
    this.updateUI();
  }

  exportCSV() {
    const rows = [
      ['Parâmetro', 'Valor'],
      ['Área (ha)', this.state.area],
      ['Produtividade (sc/ha)', this.state.produtividade],
      ['Preço Saca (R$)', this.state.preco_saca],
      ['Custo/ha (R$)', this.state.custo_ha],
      ['Custo Fixo (R$)', this.state.custo_fixo],
      ['Receita Total', this.state.receita],
      ['Custo Total', this.state.custo_total],
      ['Lucro Líquido', this.state.lucro],
      ['Margem (%)', this.state.margem.toFixed(1)],
      ['ROI (%)', this.state.roi.toFixed(1)],
    ]
      .map((r) => r.join(','))
      .join('\n');

    const blob = new Blob(['\uFEFF' + rows], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `simulador_lucro_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  loadRealData(safraId) {
    if (!safraId) return;

    fetch(`/api/financeiro/custo-producao/?safra_id=${safraId}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.error) {
          console.error('Erro ao carregar dados da safra:', data.error);
          return;
        }
        this.state.area = data.area_total_ha > 0 ? Math.round(data.area_total_ha) : 100;
        let prod_ha = 60;
        if (data.area_total_ha > 0 && data.producao_estimada > 0) {
          prod_ha = Math.round(data.producao_estimada / data.area_total_ha);
        }
        this.state.produtividade = prod_ha;
        if (data.custo_por_hectare > 0) {
          this.state.custo_ha = Math.round(data.custo_por_hectare);
        }
        this.state.custo_fixo = 0;
        Object.keys(this.state).forEach((key) => {
          const slider = this.container.querySelector(`.sim-slider[data-key="${key}"]`);
          if (slider) slider.value = this.state[key];
        });
        this.calculate();
        this.updateUI();
        if (typeof showToast === 'function') {
          showToast('success', 'Dados reais carregados com sucesso!');
        }
      })
      .catch((err) => console.error(err));
  }

  formatCurrency(v) {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL',
      maximumFractionDigits: 0,
    }).format(v);
  }

  formatNumber(v) {
    return v.toLocaleString('pt-BR', {
      minimumFractionDigits: cfg.step < 1 ? 1 : 0,
      maximumFractionDigits: 1,
    });
  }

  // Mount to container
  mount(container) {
    this.container = typeof container === 'string' ? document.getElementById(container) : container;
    this.render();
    this.bindEvents();
    return this;
  }
}

// Mount helper
window.ProfitSimulator = ProfitSimulator;

// Auto-mount if container exists
document.addEventListener('DOMContentLoaded', () => {
  const el = document.getElementById('profitSimulator');
  if (el && !el.dataset.mounted) {
    new ProfitSimulator(el);
    el.dataset.mounted = 'true';
  }
});

// Export
if (typeof module !== 'undefined') module.exports = ProfitSimulator;
