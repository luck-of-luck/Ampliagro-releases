import { readFileSync } from 'node:fs';
import { beforeEach, afterEach, expect, it, vi } from 'vitest';

const template = readFileSync('app/templates/gestao/_estoque_documento.html', 'utf8')
  .replaceAll('{{ propriedade.pk }}', '42')
  .replaceAll('{{ propriedade.nome }}', 'Fazenda teste')
  .replace("{% url 'ia-imagem-estoque' %}", '/api/ia/imagem-estoque/')
  .replace("{% url 'ia-confirmar-estoque' %}", '/api/ia/confirmar-estoque/')
  .replace('{% csrf_token %}', '<input name="csrfmiddlewaretoken" value="csrf-teste" type="hidden">');
let root;
const q = (seletor) => root.querySelector(seletor);
const enviar = (seletor) => q(seletor).dispatchEvent(new Event('submit', { cancelable: true }));
const resposta = (dados, status = 200) => ({ ok: status < 400, status, json: async () => dados });
const rascunho = {
  ok: true, artefato_id: 123,
  itens: [{ nome: 'Ureia', quantidade: '12.50', unidade: 'kg' }],
};

beforeEach(async () => {
  vi.resetModules();
  document.body.innerHTML = template;
  root = document.querySelector('[data-central-ocr]');
  vi.stubGlobal('fetch', vi.fn());
  await import('../../app/static/js/central-estoque.js');
});
afterEach(() => { vi.unstubAllGlobals(); document.body.innerHTML = ''; });

async function preparar(dados = rascunho) {
  fetch.mockResolvedValueOnce(resposta(dados));
  q('textarea').value = 'Ureia 12,50 kg';
  enviar('[data-ocr-leitura]');
  await vi.waitFor(() => expect(q('[data-ocr-revisao]').hidden).toBe(false));
}

it('exige documento ou texto antes de chamar o servidor', () => {
  enviar('[data-ocr-leitura]');
  expect(fetch).not.toHaveBeenCalled();
  expect(q('[data-ocr-status]').textContent).toContain('Selecione uma imagem');
});

it('prepara revisão sem gravar e confirma somente os valores corrigidos na propriedade selecionada', async () => {
  await preparar();
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch.mock.calls[0][0]).toBe('/api/ia/imagem-estoque/');
  expect(fetch.mock.calls[0][1].headers['X-CSRFToken']).toBe('csrf-teste');
  expect(fetch.mock.calls[0][1].body.get('texto')).toBe('Ureia 12,50 kg');
  q('[data-campo="quantidade"]').value = '15,25';
  fetch.mockResolvedValueOnce(resposta({ ok: true, resposta: 'Gravado.' }));
  enviar('[data-ocr-revisao]');
  await vi.waitFor(() => expect(q('[data-ocr-status]').textContent).toBe('Gravado.'));
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({
    artefato_id: 123, propriedade_id: 42,
    itens: [{ nome: 'Ureia', quantidade: '15,25', unidade: 'kg' }],
  });
  expect(q('[data-ocr-itens]').disabled).toBe(true);
  expect(q('[data-ocr-confirmar]').disabled).toBe(true);
  enviar('[data-ocr-revisao]');
  expect(fetch).toHaveBeenCalledTimes(2);
});

it('permite adicionar e remover itens e não envia um lote vazio', async () => {
  await preparar();
  q('[data-ocr-remover]').click();
  expect(q('[data-ocr-confirmar]').disabled).toBe(true);
  enviar('[data-ocr-revisao]');
  expect(fetch).toHaveBeenCalledTimes(1);
  q('[data-ocr-adicionar]').click();
  expect(q('[data-ocr-lista]').children).toHaveLength(1);
  expect(q('[data-campo="nome"]')).toBe(document.activeElement);
});

it('mostra aviso de OCR indisponível e oferece preenchimento sem interpretar HTML', async () => {
  await preparar({ ...rascunho, itens: [], aviso: '<b>Motor indisponível</b>' });
  expect(q('[data-ocr-status]').textContent).toContain('<b>Motor indisponível</b>');
  expect(q('[data-ocr-status] b')).toBeNull();
  expect(q('[data-ocr-lista]').children).toHaveLength(1);
});

it('mantém valores revisados e permite corrigir rejeição explícita do servidor', async () => {
  await preparar();
  q('[data-campo="quantidade"]').value = '0.001';
  fetch.mockResolvedValueOnce(resposta({ ok: false, erro: 'Corrija os itens.', campos: { itens: [{ quantidade: ['Use duas casas decimais.'] }] } }, 400));
  enviar('[data-ocr-revisao]');
  await vi.waitFor(() => expect(q('[data-ocr-status]').dataset.error).toBe('true'));
  expect(q('[data-ocr-status]').textContent).toContain('Item 1: Use duas casas decimais.');
  expect(q('[data-campo="quantidade"]').value).toBe('0.001');
  expect(q('[data-ocr-itens]').disabled).toBe(false);
});

it('evita envios simultâneos e repete exatamente o mesmo rascunho após perda de resposta', async () => {
  await preparar();
  let rejeitar;
  fetch.mockImplementationOnce(() => new Promise((_resolve, reject) => { rejeitar = reject; }));
  enviar('[data-ocr-revisao]');
  enviar('[data-ocr-revisao]');
  expect(fetch).toHaveBeenCalledTimes(2);
  rejeitar(new TypeError('Failed to fetch'));
  await vi.waitFor(() => expect(q('[data-ocr-status]').dataset.error).toBe('true'));
  expect(q('[data-ocr-itens]').disabled).toBe(true);
  expect(q('[data-ocr-novo]').disabled).toBe(true);
  fetch.mockResolvedValueOnce(resposta({ ok: true, reutilizado: true }));
  enviar('[data-ocr-revisao]');
  await vi.waitFor(() => expect(q('[data-ocr-status]').textContent).toContain('Nenhum item foi duplicado'));
  expect(fetch.mock.calls[2][1].body).toBe(fetch.mock.calls[1][1].body);
});

it('não trata erro HTML como confirmação nem perde o rascunho', async () => {
  await preparar();
  fetch.mockResolvedValueOnce({ ok: false, status: 502, json: async () => { throw new SyntaxError(); } });
  enviar('[data-ocr-revisao]');
  await vi.waitFor(() => expect(q('[data-ocr-status]').textContent).toContain('Mantenha esta página aberta'));
  expect(q('[data-ocr-confirmar]').disabled).toBe(false);
  expect(q('[data-ocr-novo]').disabled).toBe(true);
});

it('inicia outro documento somente após sair do fluxo anterior', async () => {
  await preparar();
  q('[data-ocr-novo]').click();
  expect(q('[data-ocr-revisao]').hidden).toBe(true);
  expect(q('[data-ocr-entrada]').disabled).toBe(false);
  expect(q('textarea').value).toBe('');
  await preparar({ ...rascunho, artefato_id: 456 });
  fetch.mockResolvedValueOnce(resposta({ ok: true, resposta: 'Gravado.' }));
  enviar('[data-ocr-revisao]');
  await vi.waitFor(() => expect(q('[data-ocr-status]').textContent).toBe('Gravado.'));
  expect(JSON.parse(fetch.mock.calls[2][1].body).artefato_id).toBe(456);
});
