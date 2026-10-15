import { describe, it, expect, vi } from 'vitest';

// `setup.js` faz `require('electron')` no topo. O Electron só existe dentro
// da app — o que se testa aqui sao as funcoes puras que ele exporta, entao
// o modulo e' stubado.
vi.mock('electron', () => ({
  BrowserWindow: class {},
  ipcMain: { handle: vi.fn(), removeHandler: vi.fn() },
  app: { isPackaged: false, getPath: vi.fn() },
}));

const { destinoDaApp, webURL } = await import('../../ampliagro-app/desktop/electron/setup.js');

describe('destino da janela principal', () => {
  // MEDIDO 2026-10-15: o desktop abria em `/`. Quem ainda nao tinha conta
  // via o painel — a primeira coisa que o produtor encontrava nao era uma
  // pergunta, era um painel vazio.
  it('abre no login, nunca no painel', () => {
    const destino = destinoDaApp('http://127.0.0.1:54321');
    expect(destino).toBe('http://127.0.0.1:54321/login/?primeiro=1');
  });

  it('mantem a origem — e a origem que trava a navegacao', () => {
    // `main.js` compara `new URL(destino).origin` com a do runtime para
    // decidir o que é link externo. Um destino noutra origem abriria a
    // janela fora da cobertura do CSP do Django, sem nada avisar.
    for (const base of ['http://127.0.0.1:1', 'https://ampliagro.example']) {
      const url = new URL(destinoDaApp(base));
      expect(url.origin).toBe(new URL(base).origin);
      expect(url.pathname).toBe('/login/');
    }
  });

  it('pergunta se e o primeiro acesso', () => {
    // O `?primeiro=1` e o que faz o login perguntar. Sem ele, um servidor web
    // novo aberto no `/login/` nao teria como saber que e' a primeira vez.
    expect(destinoDaApp('http://127.0.0.1:54321')).toContain('primeiro=1');
  });

  it('descarta caminho e query do destino base', () => {
    // O destino base pode vir de configuracao. `new URL('/login/', base)`
    // reescreve o caminho: um `?` ou um `/dashboard/` herdado nao sobrevive.
    expect(destinoDaApp('https://ampliagro.example/dashboard/?x=1')).toBe(
      'https://ampliagro.example/login/?primeiro=1'
    );
  });
});

describe('webURL', () => {
  it('rejeita o que o bootstrap não pode seguir', () => {
    // Um `javascript:` aqui seria navigated-to pela janela principal.
    for (const valor of [
      'http://ampliagro.example',
      'https://user:pass@ampliagro.example',
      'https://ampliagro.example#painel',
      'javascript:alert(1)',
    ]) {
      expect(() => webURL(valor)).toThrow();
    }
    expect(webURL('')).toBeNull();
    expect(webURL('https://ampliagro.example')).toBe('https://ampliagro.example/');
  });
});
