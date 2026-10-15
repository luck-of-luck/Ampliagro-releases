import { describe, it, expect } from 'vitest';
import {
  formatCurrency,
  formatNumber,
  formatArea,
  formatWeight,
  formatDate,
} from '../../app/static/js/formatters.js';

describe('formatters', () => {
  it('formats currency correctly', () => {
    const formatted = formatCurrency(1234.56, 'BRL');
    // Result will depend on locale, but it should contain 1
    expect(formatted).toContain('1');
    expect(formatted).toContain('56');
  });

  it('formats numbers with 2 decimals by default', () => {
    const formatted = formatNumber(12.345);
    expect(formatted).toContain('12');
    expect(formatted).toContain('35'); // rounded
  });

  it('formats area in ha', () => {
    expect(formatArea(50)).toContain('50');
    expect(formatArea(50)).toContain('ha');
  });

  it('formats weight in kg or t', () => {
    expect(formatWeight(500)).toContain('500');
    expect(formatWeight(500)).toContain('kg');

    expect(formatWeight(1500)).toContain('1');
    expect(formatWeight(1500)).toContain('50'); // 1.50 t
    expect(formatWeight(1500)).toContain('t');
  });
});

describe('formatters (reuso de instâncias Intl)', () => {
  // O contrato que importa: cachear a instância NÃO pode misturar parâmetros.
  // Um cache sem chave por opção devolveria "5,00" onde se pediu 0 casas —
  // estes testes travam esse comportamento observável.
  it('respeita casas decimais distintas entre chamadas', () => {
    expect(formatNumber(5)).toMatch(/5[.,]00/);
    expect(formatNumber(5, 0)).toBe('5');
    expect(formatNumber(5)).toMatch(/5[.,]00/); // volta ao cache anterior
    expect(formatNumber(5)).not.toBe(formatNumber(5, 0));
  });

  it('não mistura moedas entre chamadas', () => {
    const brl = formatCurrency(10, 'BRL');
    const usd = formatCurrency(10, 'USD');
    expect(brl).not.toBe(usd);
    expect(usd).not.toContain('R$');
  });

  it('formata datas e distingue estilos', () => {
    const iso = '2026-10-14T12:00:00Z';
    const medium = formatDate(iso, 'medium');
    const short = formatDate(iso, 'short');
    expect(medium).toMatch(/2026/);
    expect(medium).not.toBe(short);
    expect(formatDate(iso, 'medium')).toBe(medium);
  });

  it('é idempotente em chamadas repetidas', () => {
    const a = formatNumber(3.14159);
    const b = formatNumber(3.14159);
    expect(a).toBe(b);
  });
});
