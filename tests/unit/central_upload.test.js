import { beforeEach, afterEach, expect, it, vi } from 'vitest';

let form;
let status;
let button;

beforeEach(async () => {
  vi.resetModules();
  document.body.innerHTML = `<form data-central-upload data-extrato>
    <input name="conta" value="42">
    <input name="csrfmiddlewaretoken" value="test-csrf">
    <button type="submit">Importar</button><p data-upload-status></p>
  </form>`;
  form = document.querySelector('form');
  status = form.querySelector('p');
  button = form.querySelector('button');
  vi.stubGlobal('fetch', vi.fn());
  await import('../../app/static/js/central-gestao.js');
});

afterEach(() => {
  vi.unstubAllGlobals();
  document.body.innerHTML = '';
});

const enviar = () => form.dispatchEvent(new Event('submit', { cancelable: true }));

it('envia para a conta selecionada com CSRF e mostra o resultado', async () => {
  fetch.mockResolvedValue({ ok: true, json: async () => ({ ok: true, mensagem: '2 conciliadas preservadas.' }) });
  enviar();
  await vi.waitFor(() => expect(status.textContent).toBe('2 conciliadas preservadas.'));
  expect(fetch).toHaveBeenCalledWith('/api/contas-bancarias/42/importar_ofx/', expect.objectContaining({
    method: 'POST', credentials: 'same-origin', headers: { 'X-CSRFToken': 'test-csrf' },
  }));
  expect(button.disabled).toBe(false);
});

it('mostra o motivo de rejeição do arquivo sem interpretar HTML', async () => {
  fetch.mockResolvedValue({ ok: false, json: async () => ({ erro: 'Linha 3: <b>data inválida</b>' }) });
  enviar();
  await vi.waitFor(() => expect(status.dataset.error).toBe('true'));
  expect(status.textContent).toBe('Linha 3: <b>data inválida</b>');
  expect(status.querySelector('b')).toBeNull();
  expect(button.disabled).toBe(false);
});

it('evita segundo envio enquanto a resposta está pendente', async () => {
  let resolver;
  fetch.mockReturnValue(new Promise((resolve) => { resolver = resolve; }));
  enviar();
  enviar();
  expect(fetch).toHaveBeenCalledTimes(1);
  resolver({ ok: true, json: async () => ({ ok: true, mensagem: 'Importado.' }) });
  await vi.waitFor(() => expect(button.disabled).toBe(false));
});

it('orienta a conferir os registros após perda de conexão', async () => {
  fetch.mockRejectedValue(new TypeError('Failed to fetch'));
  enviar();
  await vi.waitFor(() => expect(status.dataset.error).toBe('true'));
  expect(status.textContent).toContain('Confira os registros antes de reenviar');
  expect(button.disabled).toBe(false);
});

it('trata resposta HTML do servidor sem exibir erro interno de JSON', async () => {
  fetch.mockResolvedValue({ ok: false, json: async () => { throw new SyntaxError('Unexpected token <'); } });
  enviar();
  await vi.waitFor(() => expect(status.dataset.error).toBe('true'));
  expect(status.textContent).toContain('Confira os registros antes de reenviar');
  expect(button.disabled).toBe(false);
});
