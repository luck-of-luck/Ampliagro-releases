/**
 * Ampliagro QR Code Module - Traceability & Sharing
 * Generates QR codes for: talhões, safras, tarefas, lotes, rastreabilidade completa
 */
class QRGenerator {
  constructor() {
    this.baseURL = window.location.origin;
    this.canvasCache = new Map();
  }

  // Generate QR code for any entity
  async generate(entity) {
    const data = this.buildQRData(entity);
    return this.renderQR(data);
  }

  buildQRData(entity) {
    const base = {
      v: '1.0', // version
      t: entity.type, // entity type: talhao, safra, tarefa, lote, produto
      id: entity.id, // entity ID
      ts: Date.now(), // timestamp
    };

    // Add type-specific data
    switch (entity.type) {
      case 'talhao':
        return { ...base, talhao: entity.id, fazenda: entity.fazenda_id, area: entity.area };
      case 'safra':
        return { ...base, safra: entity.id, cultura: entity.cultura_id, ano: entity.ano };
      case 'tarefa':
        return { ...base, tarefa: entity.id, estagio: entity.estagio_id, cargo: entity.cargo_alvo };
      case 'lote':
        return { ...base, lote: entity.id, produto: entity.produto_id, validade: entity.validade };
      case 'produto':
        return { ...base, produto: entity.id, lote: entity.lote_id, validade: entity.validade };
      case 'rastreabilidade':
        return { ...base, cadeia: entity.cadeia }; // full traceability chain
      default:
        return base;
    }
  }

  async renderQR(data, options = {}) {
    const {
      size = 256,
      margin = 2,
      colorDark = '#0f9d6e',
      colorLight = '#ffffff',
      logo = null,
    } = options;

    // Use cache if available
    const cacheKey = JSON.stringify(data) + size;
    if (this.canvasCache.has(cacheKey)) {
      return this.canvasCache.get(cacheKey);
    }

    // Use QRCode library if available, otherwise fallback
    if (window.QRCode) {
      return this.renderWithLibrary(data, options);
    }

    // Fallback: simple canvas QR (basic)
    return this.renderFallback(data, options);
  }

  async renderWithLibrary(data, options) {
    const {
      size = 256,
      margin = 2,
      colorDark = '#0f9d6e',
      colorLight = '#ffffff',
      logo = null,
    } = options;

    const canvas = document.createElement('canvas');
    canvas.width = options.size || 256;
    canvas.height = options.size || 256;

    return new Promise((resolve, reject) => {
      QRCode.toCanvas(
        canvas,
        JSON.stringify(data),
        {
          width: options.size,
          margin: options.margin,
          color: {
            dark: options.colorDark,
            light: options.colorLight,
          },
          errorCorrectionLevel: 'M',
        },
        (error) => {
          if (error) reject(error);
          else {
            if (options.logo) {
              this.addLogo(canvas, options.logo)
                .then(() => resolve(canvas))
                .catch(reject);
            } else {
              resolve(canvas);
            }
          }
        }
      );
    });
  }

  async addLogo(canvas, logoUrl) {
    return new Promise((resolve) => {
      const img = new Image();
      img.crossOrigin = 'anonymous';
      img.onload = () => {
        const ctx = canvas.getContext('2d');
        const logoSize = canvas.width * 0.2;
        const x = (canvas.width - logoSize) / 2;
        const y = (canvas.height - logoSize) / 2;

        // White background behind logo
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(x - 4, y - 4, logoSize + 8, logoSize + 8);

        ctx.drawImage(img, x, y, logoSize, logoSize);
        resolve(canvas);
      };
      img.src = logoUrl;
    });
  }

  renderFallback(data, options) {
    // Very basic fallback - returns data URL placeholder
    const canvas = document.createElement('canvas');
    canvas.width = options.size || 256;
    canvas.height = options.size || 256;
    const ctx = canvas.getContext('2d');

    // White background
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw pattern (placeholder for actual QR)
    ctx.fillStyle = '#0f9d6e';
    const blockSize = canvas.width / 25;
    const pattern = this.generateQRPattern(JSON.stringify(data));

    for (let y = 0; y < 25; y++) {
      for (let x = 0; x < 25; x++) {
        if (pattern[y * 25 + x]) {
          ctx.fillRect(x * blockSize, y * blockSize, blockSize, blockSize);
        }
      }
    }

    return canvas.toDataURL('image/png');
  }

  generateQRPattern(str) {
    // Simple deterministic pattern from string hash
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = (hash << 5) - hash + str.charCodeAt(i);
      hash |= 0;
    }

    const pattern = new Array(625).fill(false);
    const rng = this.mulberry32(Math.abs(hash));

    // Finder patterns (corners)
    this.drawFinder(pattern, 0, 0);
    this.drawFinder(pattern, 18, 0);
    this.drawFinder(pattern, 0, 18);

    // Fill rest with pseudo-random based on hash
    for (let i = 0; i < 625; i++) {
      if (!this.isFinderArea(i)) {
        pattern[i] = rng() > 0.5;
      }
    }

    return pattern;
  }

  mulberry32(a) {
    return function () {
      let t = (a += 0x6d2b79f5);
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  drawFinder(pattern, x, y) {
    const positions = [
      [0, 0],
      [1, 0],
      [2, 0],
      [3, 0],
      [4, 0],
      [5, 0],
      [6, 0],
      [0, 1],
      [6, 1],
      [0, 2],
      [6, 2],
      [0, 3],
      [6, 3],
      [0, 4],
      [6, 4],
      [0, 5],
      [6, 5],
      [0, 6],
      [1, 6],
      [2, 6],
      [3, 6],
      [4, 6],
      [5, 6],
      [6, 6],
    ];
    positions.forEach(([dx, dy]) => {
      const idx = (y + dy) * 25 + (x + dx);
      if (idx >= 0 && idx < 625) pattern[idx] = true;
    });
  }

  isFinderArea(i) {
    const x = i % 25;
    const y = Math.floor(i / 25);
    return (x <= 6 && y <= 6) || (x >= 18 && y <= 6) || (x <= 6 && y >= 18);
  }

  // Generate QR for specific Ampliagro entities
  async generateTalhaoQR(talhao) {
    return this.generate({
      type: 'talhao',
      id: talhao.id,
      fazenda_id: talhao.fazenda_id,
      area: talhao.area_hectare,
    });
  }

  async generateSafraQR(safra) {
    return this.generate({
      type: 'safra',
      id: safra.id,
      cultura_id: safra.cultura_id,
      ano: safra.ano,
    });
  }

  async generateTarefaQR(tarefa) {
    return this.generate({
      type: 'tarefa',
      id: tarefa.id,
      estagio_id: tarefa.estagio_id,
      cargo_alvo: tarefa.cargo_alvo,
    });
  }

  async generateLoteQR(lote) {
    return this.generate({
      type: 'lote',
      id: lote.id,
      produto_id: lote.produto_id,
      validade: lote.validade,
    });
  }

  // Full traceability chain QR
  async generateRastreabilidade(lote) {
    // Build full chain: produto -> lote -> safra -> talhão -> fazenda
    const cadeia = await this.buildCadeiaRastreabilidade(lote);
    return this.generate({
      type: 'rastreabilidade',
      id: lote.id,
      cadeia: cadeia,
    });
  }

  async buildCadeiaRastreabilidade(lote) {
    // This would fetch from API in production
    // For now return structure
    return {
      produto: { id: lote.produto_id, nome: 'Produto' },
      lote: { id: lote.id, validade: lote.validade },
      safra: { id: null, cultura: null, ano: null },
      talhao: { id: null, nome: null, area: null },
      fazenda: { id: null, nome: null },
    };
  }

  // Batch generate for multiple entities
  async generateBatch(entities) {
    const results = [];
    for (const entity of entities) {
      try {
        const qr = await this.generate(entity);
        results.push({ entity: entity.id, qr: qr, success: true });
      } catch (error) {
        results.push({ entity: entity.id, success: false, error: error.message });
      }
    }
    return results;
  }

  // Create printable QR sheet
  async createPrintSheet(entities, options = {}) {
    const { cols = 3, size = 200, margin = 10, showLabel = true } = options;
    const qrs = await this.generateBatch(entities);

    const canvas = document.createElement('canvas');
    const rows = Math.ceil(qrs.length / cols);
    const cellSize = size + 40; // space for label
    canvas.width = cols * cellSize + (cols + 1) * margin;
    canvas.height = rows * cellSize + (rows + 1) * margin;

    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    for (let i = 0; i < qrs.length; i++) {
      const col = i % cols;
      const row = Math.floor(i / cols);
      const x = margin + col * cellSize;
      const y = margin + row * cellSize;

      const qr = qrs[i].qr;
      if (qr instanceof HTMLCanvasElement) {
        ctx.drawImage(qr, x, y, size, size);
      } else if (typeof qr === 'string') {
        const img = new Image();
        await new Promise((resolve) => {
          img.onload = resolve;
          img.src = qr;
        });
        ctx.drawImage(img, x, y, size, size);
      }

      if (options.showLabel) {
        ctx.fillStyle = '#1e293b';
        ctx.font = '12px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(qrs[i].entity.id || 'QR', x + size / 2, y + size + 20);
      }
    }

    return canvas.toDataURL('image/png');
  }
}

// Global instance
window.QRGenerator = new QRGenerator();

// React/Vue component helper
window.generateQR = (entity, options) => window.QRGenerator.generate(entity, options);
window.generateQRBatch = (entities, options) => window.QRGenerator.generateBatch(entities, options);
window.createQRSheet = (entities, options) =>
  window.QRGenerator.createPrintSheet(entities, options);

// Export
if (typeof module !== 'undefined' && module.exports) {
  module.exports = QRGenerator;
}
