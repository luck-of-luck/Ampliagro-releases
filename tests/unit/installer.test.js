import { readFileSync } from 'node:fs';
import { describe, it, expect, vi, afterEach } from 'vitest';

const html = readFileSync('installer.html', 'utf8');
const source = readFileSync('installer.js', 'utf8');
async function render(save = vi.fn().mockResolvedValue({ ok: true }), options = {}) {
  document.documentElement.innerHTML = html;
  window.ampliagroSetup = {
    read: vi.fn().mockResolvedValue({
      terms: 'Licença real',
      termsHash: 'hash',
      ...options,
      grupos: [
        {
          rotulo: 'Grãos',
          culturas: [
            { id: 1, nome: 'Café' },
            { id: 2, nome: '<img onerror=alert(1)>' },
          ],
        },
      ],
    }),
    save,
    open: vi.fn().mockResolvedValue(),
  };
  window.eval(`(() => {${source}\n})()`);
  await vi.waitFor(() => expect(document.querySelector('#terms').textContent).toBe('Licença real'));
  return window.ampliagroSetup;
}
const click = (id) => document.getElementById(id).click();
afterEach(() => {
  delete window.ampliagroSetup;
  localStorage.clear();
});
describe('assistente de instalação', () => {
  it('reabre o aceite na reinstalação manual e preserva as culturas escolhidas', async () => {
    const api = await render(undefined, {
      forceSetup: true,
      installation: { termsHash: 'hash', acceptedAt: '2026-10-15', culturas: [1] },
    });
    expect(api.open).not.toHaveBeenCalled();
    expect(document.querySelector('#step-0').hidden).toBe(false);
    expect(document.querySelector('#next').disabled).toBe(true);
    expect(document.querySelector('#cultures input').checked).toBe(true);
  });
  it('exige aceite, seleciona do catálogo e só conclui após persistir', async () => {
    const api = await render();
    expect(document.querySelector('#next').disabled).toBe(true);
    click('accepted');
    click('next');
    expect(document.querySelector('input[value=cloud]').disabled).toBe(true);
    click('next');
    expect(document.querySelector('#next').disabled).toBe(true);
    const search = document.querySelector('#search');
    search.value = 'cafe';
    search.dispatchEvent(new Event('input'));
    document.querySelector('#cultures input').click();
    click('next');
    await vi.waitFor(() => expect(document.querySelector('#step-3').hidden).toBe(false));
    expect(api.save).toHaveBeenCalledWith({
      accepted: true,
      termsHash: 'hash',
      mode: 'local',
      culturas: [1],
    });
    click('next');
    expect(api.open).toHaveBeenCalledOnce();
  });
  it('não interpreta nomes como HTML e mantém erro de gravação visível', async () => {
    await render(vi.fn().mockRejectedValue(new Error('Disco cheio')));
    expect(document.querySelector('#cultures img')).toBeNull();
    click('accepted');
    click('next');
    click('next');
    document.querySelector('#cultures input').click();
    click('next');
    await vi.waitFor(() =>
      expect(document.querySelector('#error').textContent).toBe('Disco cheio')
    );
    expect(document.querySelector('#step-3').hidden).toBe(true);
    expect(document.querySelector('#next').disabled).toBe(false);
  });
});
