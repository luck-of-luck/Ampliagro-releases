import { describe, it, expect } from 'vitest';
import '../../app/static/js/report.js';

describe('ReportGenerator.formatCurrency (reuso da instância Intl)', () => {
  const rg = new window.ReportGenerator();

  it('formata em BRL e é idempotente', () => {
    const a = rg.formatCurrency(1234.5);
    const b = rg.formatCurrency(1234.5);
    expect(a).toBe(b);
    expect(a).toContain('R$');
    expect(a).toContain('1.234,50');
  });

  it('não mistura valores entre chamadas (cache não vaza estado)', () => {
    expect(rg.formatCurrency(10)).not.toBe(rg.formatCurrency(20));
  });

  it('lida com zero e negativos', () => {
    expect(rg.formatCurrency(0)).toContain('R$');
    expect(rg.formatCurrency(-42.7)).toContain('-');
  });
});
