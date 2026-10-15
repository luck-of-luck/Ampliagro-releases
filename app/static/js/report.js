/**
 * Ampliagro PDF Report Generator - 1-click reports with photos, telemetry, QR
 * Uses jsPDF + autoTable + QRCode
 */
const _brlFmt = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
class ReportGenerator {
  constructor() {
    this.doc = null;
    this.pageHeight = 297; // A4 mm
    this.pageWidth = 210;
    this.margin = 20;
    this.y = 20;
  }

  async generateReport(config) {
    const {
      propriedade,
      periodo = 'ultimo_mes',
      incluir_fotos = true,
      incluir_telemetria = true,
      incluir_financeiro = true,
      incluir_tarefas = true,
      incluir_alertas = true,
      incluir_qr = true,
      formato = 'A4',
      logo_url = null,
    } = config;

    // Dynamic import jsPDF
    const { jsPDF } =
      await import('https://cdn.jsdelivr.net/npm/jspdf@2.5.1/dist/jspdf.umd.min.js');
    const autoTable = (
      await import('https://cdn.jsdelivr.net/npm/jspdf-autotable@3.8.1/dist/jspdf.plugin.autotable.min.js')
    ).default;

    this.doc = new jsPDF({ unit: 'mm', format: formato });
    this.pageHeight = this.doc.internal.pageSize.getHeight();
    this.pageWidth = this.doc.internal.pageSize.getWidth();
    this.margin = 20;
    this.y = 20;

    // Load logo if provided
    let logoData = null;
    if (logo_url) {
      try {
        const response = await fetch(logo_url);
        const blob = await response.blob();
        logoData = await this.blobToBase64(blob);
      } catch (e) {
        console.warn('Could not load logo:', e);
      }
    }

    // Load QRCode library
    await this.loadQRCode();

    // Fetch data
    const data = await this.fetchReportData(propriedade, periodo, {
      incluir_fotos,
      incluir_telemetria,
      incluir_financeiro,
      incluir_tarefas,
      incluir_alertas,
    });

    // Build report
    this.addCoverPage(propriedade, periodo, logoData);

    if (incluir_telemetria) this.addTelemetrySection(data.telemetria);
    if (incluir_financeiro) this.addFinancialSection(data.financeiro);
    if (incluir_tarefas) this.addTasksSection(data.tarefas);
    if (incluir_alertas) this.addAlertsSection(data.alertas);
    if (incluir_fotos) this.addPhotosSection(data.fotos);

    if (incluir_qr) this.addQRSection(propriedade);

    // Save
    const filename = `Relatorio_${propriedade.nome.replace(/\s+/g, '_')}_${
      new Date().toISOString().split('T')[0]
    }.pdf`;
    this.doc.save(filename);

    return { success: true, filename };
  }

  async loadQRCode() {
    if (window.QRCode) return;
    await new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js';
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }

  blobToBase64(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  async fetchReportData(propriedade, periodo, options) {
    // In production, fetch from API
    // For now return mock structure
    return {
      telemetria: await this.fetchTelemetria(propriedade, periodo),
      financeiro: await this.fetchFinanceiro(propriedade, periodo),
      tarefas: await this.fetchTarefas(propriedade, periodo),
      alertas: await this.fetchAlertas(propriedade),
      fotos: await this.fetchFotos(propriedade),
    };
  }

  async fetchTelemetria(propriedade, periodo) {
    try {
      const r = await fetch(`/api/telemetria/?propriedade=${propriedade}&periodo=${periodo}`);
      const j = await r.json();
      return j.results || j || [];
    } catch {
      return [];
    }
  }

  async fetchFinanceiro(propriedade, periodo) {
    try {
      const r = await fetch(`/api/financeiro/?propriedade=${propriedade}&periodo=${periodo}`);
      return await r.json();
    } catch {
      return {
        receitas: [],
        despesas: [],
        resumo: { receita_total: 0, despesa_total: 0, lucro: 0 },
      };
    }
  }

  async fetchTarefas(propriedade, periodo) {
    try {
      const r = await fetch(`/api/tarefas-estagio/?propriedade=${propriedade}&periodo=${periodo}`);
      const j = await r.json();
      return j.results || j || [];
    } catch {
      return [];
    }
  }

  async fetchAlertas(propriedade) {
    try {
      const r = await fetch(`/api/alertas-telemetria/?propriedade=${propriedade}`);
      const j = await r.json();
      return j.results || j || [];
    } catch {
      return [];
    }
  }

  async fetchFotos(propriedade) {
    return [];
  }

  addCoverPage(propriedade, periodo, logoData) {
    // Background
    this.doc.setFillColor(15, 157, 110);
    this.doc.rect(0, 0, this.pageWidth, this.pageHeight, 'F');

    // Logo
    if (logoData) {
      this.doc.addImage(logoData, 'PNG', this.margin, this.y, 40, 40);
    }

    // Title
    this.doc.setFontSize(36);
    this.doc.setTextColor(255, 255, 255);
    this.doc.setFont('helvetica', 'bold');
    this.doc.text('Relatório Gerencial', this.pageWidth / 2, this.y + 30, { align: 'center' });

    this.y += 50;
    this.doc.setFontSize(24);
    this.doc.setFont('helvetica', 'normal');
    this.doc.text(propriedade.nome, this.pageWidth / 2, this.y, { align: 'center' });

    this.y += 15;
    this.doc.setFontSize(14);
    this.doc.setFont('helvetica', 'light');
    this.doc.text(`Período: ${this.formatPeriodo(periodo)}`, this.pageWidth / 2, this.y, {
      align: 'center',
    });
    this.doc.text(
      `Gerado em: ${new Date().toLocaleDateString('pt-BR')}`,
      this.pageWidth / 2,
      this.y + 10,
      { align: 'center' }
    );

    // QR code on cover
    const qrData = `ampliagro://propriedade/${propriedade.id}`;
    this.addQRCode(qrCode, this.pageWidth - 50, 20, 30);

    this.addPage();
  }

  addTelemetrySection(data) {
    this.addSectionTitle('Telemetria & Clima');

    if (!data.length) {
      this.doc.text('Nenhum dado de telemetria disponível.', this.margin, this.y);
      this.y += 10;
      return;
    }

    // Summary stats
    const temps = data.map((d) => d.temperatura).filter((v) => v !== undefined);
    const umids = data.map((d) => d.umidade).filter((v) => v !== undefined);
    const chuvas = data.map((d) => d.chuva).filter((v) => v !== undefined);

    const stats = [
      ['Métrica', 'Mín', 'Máx', 'Média', 'Total'],
      ['Temp (°C)', Math.min(...temps), Math.max(...temps), this.mean(temps).toFixed(1), '-'],
      ['Umidade (%)', Math.min(...umids), Math.max(...umids), this.mean(umids).toFixed(1), '-'],
      ['Chuva (mm)', Math.min(...chuvas), Math.max(...chuvas), '-', this.sum(chuvas).toFixed(1)],
      [
        'Radiação (W/m²)',
        Math.min(...data.map((d) => d.radiacao).filter((v) => v !== undefined)),
        Math.max(...data.map((d) => d.radiacao).filter((v) => v !== undefined)),
        this.mean(data.map((d) => d.radiacao).filter((v) => v !== undefined)).toFixed(0),
        '-',
      ],
    ];

    this.doc.autoTable({
      startY: this.y,
      head: [stats[0]],
      body: stats.slice(1),
      theme: 'striped',
      headStyles: { fillColor: [15, 157, 110] },
      margin: { left: this.margin, right: this.margin },
    });

    this.y = this.doc.lastAutoTable.finalY + 10;

    // Temperature chart (simple ASCII-style or use chart.js if available)
    this.addMiniChart(
      'Temperatura (°C)',
      data.map((d) => ({ x: d.data, y: d.temperatura })).filter((p) => p.y !== undefined)
    );
    this.y += 5;
  }

  addFinancialSection(data) {
    this.addPage();
    this.addSectionTitle('Resumo Financeiro');

    const { receitas, despesas, resumo } = data;

    // Summary cards
    this.addSummaryCards([
      {
        label: 'Receita Total',
        value: this.formatCurrency(resumo.receita_total),
        color: [15, 157, 110],
      },
      {
        label: 'Despesa Total',
        value: this.formatCurrency(resumo.despesa_total),
        color: [220, 38, 38],
      },
      { label: 'Lucro', value: this.formatCurrency(resumo.lucro), color: [15, 157, 110] },
    ]);

    this.y += 10;

    // Receitas table
    if (receitas.length) {
      this.addTableSection(
        'Receitas',
        receitas.map((r) => [r.data, r.descricao, r.categoria, this.formatCurrency(r.valor)]),
        ['Data', 'Descrição', 'Categoria', 'Valor']
      );
    }

    // Despesas table
    if (despesas.length) {
      this.addTableSection(
        'Despesas',
        despesas.map((d) => [d.data, d.descricao, d.categoria, this.formatCurrency(d.valor)]),
        ['Data', 'Descrição', 'Categoria', 'Valor']
      );
    }
  }

  addTasksSection(tarefas) {
    this.addPage();
    this.addSectionTitle('Quadro de Tarefas');

    const cols = ['Tarefa', 'Área', 'Status', 'Prioridade', 'Prazo', 'Responsável'];
    const rows = tarefas.map((t) => [
      t.descricao,
      t.cargo_alvo || 'Geral',
      t.status,
      t.prioridade,
      t.data_limite || '-',
      t.responsavel || '-',
    ]);

    this.doc.autoTable({
      startY: this.y,
      head: [cols],
      body: rows,
      theme: 'striped',
      headStyles: { fillColor: [15, 157, 110] },
      margin: { left: this.margin, right: this.margin },
      styles: { fontSize: 9, cellPadding: 3 },
      columnStyles: { 0: { cellWidth: 60 } },
    });

    this.y = this.doc.lastAutoTable.finalY + 10;
  }

  addAlertsSection(alertas) {
    this.addSectionTitle('Alertas Recentes');

    if (!alertas.length) {
      this.doc.text('Nenhum alerta no período.', this.margin, this.y);
      this.y += 10;
      return;
    }

    const rows = alertas.map((a) => [
      a.timestamp.split('T')[0],
      a.metric,
      a.valor,
      a.severidade.toUpperCase(),
      a.mensagem,
    ]);

    this.doc.autoTable({
      startY: this.y,
      head: [['Data', 'Métrica', 'Valor', 'Severidade', 'Mensagem']],
      body: rows,
      theme: 'striped',
      headStyles: { fillColor: [220, 38, 38] },
      margin: { left: this.margin, right: this.margin },
      columnStyles: { 3: { cellWidth: 25 }, 4: { cellWidth: 60 } },
    });

    this.y = this.doc.lastAutoTable.finalY + 10;
  }

  addPhotosSection(fotos) {
    if (!fotos.length) return;

    this.addPage();
    this.addSectionTitle('Registros Fotográficos');

    const cols = 2;
    const imgSize = 80;
    const gap = 10;

    fotos.forEach((foto, i) => {
      const col = i % 2;
      const row = Math.floor(i / 2);
      const x = this.margin + col * (imgSize + 10);
      const y = this.y + row * (imgSize + 15);

      if (y + imgSize > this.pageHeight - this.margin) {
        this.addPage();
        this.y = this.margin;
      }

      try {
        this.doc.addImage(
          foto.url,
          'JPEG',
          this.margin + (i % 2) * (imgSize + 10),
          this.y + Math.floor(i / 2) * (imgSize + 15),
          imgSize,
          imgSize
        );
        this.doc.setFontSize(8);
        this.doc.text(foto.legenda, this.margin + (i % 2) * (imgSize + 10), this.y + imgSize + 5);
      } catch (e) {
        console.warn('Could not add image:', foto.url);
      }
    });

    this.y += Math.ceil(fotos.length / 2) * (imgSize + 15) + 10;
  }

  addQRSection(propriedade) {
    this.addPage();
    this.addSectionTitle('Rastreabilidade - QR Codes');

    const qrData = `ampliagro://propriedade/${propriedade.id}`;
    this.addQRCode(qrCode, this.margin, this.y, 50);

    this.doc.setFontSize(10);
    this.doc.text('Escaneie para acessar a fazenda no app', this.margin, this.y + 55);

    this.y += 65;
    this.doc.text('Este QR code dá acesso direto à fazenda no Ampliagro.', this.margin, this.y);
    this.doc.text(
      'Útil para rastreabilidade de lotes, auditorias e certificações.',
      this.margin,
      this.y + 6
    );
  }

  addSectionTitle(title) {
    this.doc.setFontSize(16);
    this.doc.setFont('helvetica', 'bold');
    this.doc.setTextColor(15, 157, 110);
    this.doc.text(title, this.margin, this.y);
    this.y += 10;
    this.doc.setDrawColor(15, 157, 110);
    this.doc.setLineWidth(0.5);
    this.doc.line(this.margin, this.y - 2, this.pageWidth - this.margin, this.y - 2);
    this.y += 5;
  }

  addPage() {
    this.doc.addPage();
    this.y = this.margin;
  }

  addSummaryCards(cards) {
    const cardWidth = 55;
    const gap = 8;
    const startX = this.margin;
    const cardHeight = 22;

    cards.forEach((card, i) => {
      const x = this.margin + i * (cardWidth + 8);
      const y = this.y;

      // Card background
      this.doc.setFillColor(255, 255, 255);
      this.doc.setDrawColor(200, 200, 200);
      this.doc.roundedRect(this.margin + i * (cardWidth + 8), this.y, 55, 22, 3, 3, 'FD');

      // Color bar
      this.doc.setFillColor(...card.color);
      this.doc.rect(this.margin + i * (cardWidth + 8) + 2, this.y + 2, 4, 18, 'F');

      // Label
      this.doc.setFontSize(8);
      this.doc.setTextColor(100, 100, 100);
      this.doc.text(card.label, this.margin + i * (cardWidth + 8) + 8, this.y + 6);

      // Value
      this.doc.setFontSize(12);
      this.doc.setFont('helvetica', 'bold');
      this.doc.setTextColor(30, 30, 30);
      this.doc.text(card.value, this.margin + i * (cardWidth + 8) + 8, this.y + 15);
    });

    this.y += 28;
  }

  addTableSection(title, rows, headers) {
    this.addSectionTitle(title);

    const { jsPDF } = require('jspdf');
    const autoTable = require('jspdf-autotable');

    this.doc.autoTable({
      startY: this.y,
      head: [headers],
      body: rows,
      theme: 'striped',
      headStyles: { fillColor: [15, 157, 110] },
      margin: { left: this.margin, right: this.margin },
      styles: { fontSize: 9, cellPadding: 2 },
      didDrawPage: (data) => {
        if (data.pageNumber > 1) {
          this.doc.setFontSize(8);
          this.doc.text(`Relatório Ampliagro - Página ${data.pageNumber}`, this.pageWidth / 2, 10, {
            align: 'center',
          });
        }
      },
    });

    this.y = this.doc.lastAutoTable.finalY + 10;
  }

  addMiniChart(title, points) {
    this.doc.setFontSize(10);
    this.doc.setTextColor(100, 100, 100);
    this.doc.text(title, this.margin, this.y);
    this.y += 5;

    // Simple ASCII-style sparkline
    if (!points.length) return;

    const canvas = document.createElement('canvas');
    canvas.width = 170;
    canvas.height = 40;
    const ctx = canvas.getContext('2d');

    const values = points.map((p) => p.y).filter((v) => v !== undefined);
    if (!values.length) return;

    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;

    ctx.strokeStyle = '#0f9d6e';
    ctx.lineWidth = 2;
    ctx.beginPath();

    points.forEach((p, i) => {
      if (p.y === undefined) return;
      const x = (i / (points.length - 1)) * 160 + 5;
      const y = 35 - ((p.y - min) / (max - min || 1)) * 30;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Add points
    points.forEach((p, i) => {
      if (p.y === undefined) return;
      const x = (i / (points.length - 1)) * 160 + 5;
      const y = 35 - ((p.y - min) / (max - min || 1)) * 30;
      ctx.beginPath();
      ctx.arc(x, y, 2, 0, 2 * Math.PI);
      ctx.fillStyle = '#0f9d6e';
      ctx.fill();
    });

    const imgData = canvas.toDataURL('image/png');
    this.doc.addImage(imgData, 'PNG', this.margin, this.y, 170, 40);
    this.y += 45;
  }

  async addQRCode(data, x, y, size) {
    if (window.QRCode) {
      const canvas = document.createElement('canvas');
      await new Promise((resolve) => {
        QRCode.toCanvas(
          canvas,
          data,
          {
            width: size,
            margin: 1,
            color: { dark: '#0f9d6e', light: '#ffffff' },
          },
          () => resolve()
        );
      });
      this.doc.addImage(canvas.toDataURL('image/png'), 'PNG', x, y, size, size);
    } else {
      // Fallback text
      this.doc.setFontSize(8);
      this.doc.setFont('courier', 'normal');
      this.doc.text(`QR: ${data}`, x, y);
    }
  }

  formatCurrency(value) {
    return _brlFmt.format(value);
  }

  formatPeriodo(periodo) {
    const map = {
      ultimo_mes: 'Último mês',
      ultimos_3_meses: 'Últimos 3 meses',
      ultimo_ano: 'Último ano',
      safra_atual: 'Safra atual',
    };
    return map[periodo] || periodo;
  }

  mean(arr) {
    return arr.reduce((a, b) => a + b, 0) / arr.length;
  }
  sum(arr) {
    return arr.reduce((a, b) => a + b, 0);
  }

  // Export
  static async generate(config) {
    const generator = new ReportGenerator();
    return generator.generateReport(config);
  }
}

// Global
window.ReportGenerator = ReportGenerator;
if (typeof module !== 'undefined') module.exports = ReportGenerator;
