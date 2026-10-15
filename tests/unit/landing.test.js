import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, it, expect, vi, afterEach } from 'vitest';

const html = readFileSync(resolve('landing.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const prefix = 'https://github.com/luck-of-luck/Ampliagro-releases/releases/download/v1/';
async function render(response, ok = true, local = false) {
  document.documentElement.innerHTML = html;
  vi.stubGlobal('location', { hostname: local ? '127.0.0.1' : 'ampliagro.example' });
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok, json: async () => response }));
  window.eval(script);
  await vi.waitFor(() =>
    expect(document.querySelector('#release-status').textContent).not.toContain('Consultando')
  );
}
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});
describe('landing pública', () => {
  it('na prévia local oferece o novo exe sem buscar a release antiga', async () => {
    const sha256 = 'a'.repeat(64);
    const url = '/downloads/Ampliagro-Instalador-Novo-x64.exe?sha256=' + sha256;
    await render({ sha256, url, size: 183900998 }, true, true);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][0]).toBe('/downloads/local.json');
    expect(document.querySelector('#downloads-windows a').getAttribute('href')).toBe(url);
    expect(document.querySelector('#downloads-windows').textContent).toContain(
      'não possui assinatura'
    );
    expect(document.querySelector('#downloads-macos a')).toBeNull();
  });
  it('não retorna ao exe antigo quando o instalador local falta ou o link é inválido', async () => {
    for (const [response, ok] of [
      [{}, false],
      [{ sha256: 'a'.repeat(64), size: 10, url: 'https://evil.example/app.exe' }, true],
    ]) {
      await render(response, ok, true);
      expect(document.querySelector('#downloads-windows a')).toBeNull();
      expect(document.querySelector('#release-status').textContent).toContain('indisponível');
    }
  });
  it('oferece apenas assets publicados com tamanho real, incluindo os dois formatos Linux', async () => {
    await render({
      tag_name: 'v1',
      assets: ['Ampliagro-x64.exe', 'Ampliagro-x86_64.AppImage', 'Ampliagro-amd64.deb'].map(
        (name) => ({ name, size: 1048576, browser_download_url: prefix + name })
      ),
    });
    expect(document.querySelectorAll('.asset-link')).toHaveLength(3);
    expect(document.querySelector('#downloads-windows').textContent).toContain('instalador');
    expect(document.querySelector('#downloads-windows').textContent).toContain('1 MB');
    expect(document.querySelector('#downloads-macos').textContent).toContain(
      'Nenhum arquivo compatível'
    );
    expect(document.querySelector('#downloads-macos a').href).toContain('/releases/latest');
    expect(document.querySelector('#downloads-linux').querySelectorAll('a')).toHaveLength(2);
  });
  it('mantém os links de fallback quando a API falha', async () => {
    await render({}, false);
    expect(document.querySelector('#release-status').textContent).toContain('Não foi possível');
    expect(document.querySelectorAll('.download-links a')).toHaveLength(3);
    expect(document.querySelectorAll('.asset-link')).toHaveLength(0);
  });
  it('rejeita metadados inválidos e mantém a navegação', async () => {
    await render({ tag_name: 'v1', assets: null });
    expect(document.querySelector('#release-status').textContent).toContain('Não foi possível');
  });
  it('não insere HTML da release nem links de outros domínios', async () => {
    await render({
      tag_name: '<img src=x onerror=alert(1)>',
      assets: [
        { name: 'Ampliagro-x64.exe', browser_download_url: 'https://evil.example/file.exe' },
      ],
    });
    expect(document.querySelector('#release-status img')).toBeNull();
    expect(document.querySelectorAll('.asset-link')).toHaveLength(0);
  });
  it('tem destinos para todas as âncoras e conteúdo útil sem JavaScript', () => {
    document.documentElement.innerHTML = html;
    for (const link of document.querySelectorAll('a[href^="#"]')) {
      expect(document.getElementById(link.getAttribute('href').slice(1))).not.toBeNull();
    }
    expect(document.querySelectorAll('h1')).toHaveLength(1);
    expect(document.querySelectorAll('details')).toHaveLength(6);
    expect(document.querySelectorAll('.download-links a')).toHaveLength(3);
  });
});

describe('cabecalho da landing', () => {
  // MEDIDO 2026-10-15: o `<link rel="icon">` trazia um data URI com aspas
  // CRUAS no `d='...'` do SVG (`...105Z" fill=...`). Uma aspa fecha o
  // atributo `href` a meio, o resto da linha passa a ser lido como
  // atributos e o HTML vaza para o corpo: a pagina abria com o texto
  // ` type="image/svg+xml" />` no topo, antes de qualquer conteudo.
  it('mantem o favicon dentro do atributo e nao vaza HTML para o corpo', () => {
    document.documentElement.innerHTML = html;
    const iconos = [...document.querySelectorAll('link[rel="icon"]')];
    expect(iconos).toHaveLength(1);
    const href = iconos[0].getAttribute('href');
    expect(href.startsWith('data:image/svg+xml,')).toBe(true);
    // O data URI tem de estar percent-encoded inteiro: nenhuma aspa, nem
    // simples, pode sobrar -- e' o que encerra o atributo.
    expect(href).not.toMatch(/["']/);
    // Nada do atributo pode reaparecer como texto no documento.
    expect(document.body.textContent).not.toContain('type="image/svg+xml"');
  });
});

describe('altern�ncia de tema', () => {
  it('alterna nos dois sentidos e restaura a escolha ao reabrir', async () => {
    await render({}, false);
    const button = document.getElementById('theme-toggle');
    expect(button.hidden).toBe(false);
    button.click();
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(button.getAttribute('aria-label')).toBe('Ativar modo claro');
    await render({}, false);
    expect(document.documentElement.dataset.theme).toBe('dark');
    document.getElementById('theme-toggle').click();
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(localStorage.getItem('ampliagro-landing-theme')).toBe('light');
  });
  it('segue o navegador sem prefer�ncia e permite sobrepor o modo escuro', async () => {
    vi.stubGlobal('matchMedia', () => ({ matches: true, addEventListener: vi.fn() }));
    await render({}, false);
    expect(document.documentElement.dataset.theme).toBe('dark');
    document.getElementById('theme-toggle').click();
    expect(document.documentElement.dataset.theme).toBe('light');
  });
  it('continua alternando quando o armazenamento est� bloqueado', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    await render({}, false);
    document.getElementById('theme-toggle').click();
    expect(document.documentElement.dataset.theme).toBe('dark');
  });
});

describe('demonstração visual', () => {
  it('exibe somente a etapa escolhida e permite voltar ao planejamento', async () => {
    await render({}, false);
    const buttons = [...document.querySelectorAll('[data-demo]')];
    expect(document.querySelector('.demo-controls').hidden).toBe(false);
    for (const button of [buttons[1], buttons[2], buttons[0]]) {
      button.click();
      expect(button.getAttribute('aria-pressed')).toBe('true');
      expect(document.querySelectorAll('.demo-stage:not([hidden])')).toHaveLength(1);
      expect(document.getElementById(button.getAttribute('aria-controls')).hidden).toBe(false);
    }
    expect(document.querySelector('.demo-disclaimer').textContent).toContain('não uma captura');
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});

describe('cenas da operação', () => {
  it('abre a cena correspondente a cada benefício sem requisições adicionais', async () => {
    await render({}, false);
    for (const link of document.querySelectorAll('[data-scene-link]')) {
      link.click();
      expect(document.getElementById('demo-' + link.dataset.sceneLink).hidden).toBe(false);
      expect(document.querySelectorAll('.demo-stage:not([hidden])')).toHaveLength(1);
    }
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
