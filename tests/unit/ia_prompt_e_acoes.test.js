/**
 * O contrato, do lado do browser. Testa o MÓDULO REAL, não uma cópia.
 *
 * Por que este ficheiro importa `ia-local.js` e o outro reproduz a lógica
 * ---------------------------------------------------------------------
 * `ia_comunicacao.test.js` copiava os blocos porque não conseguia importar o
 * ficheiro. Este consegue — e a diferença é a diferença entre testar o
 * código e testar uma transcrição dele. Se alguém voltar a escrever
 * `POST /api/iot/comandos/` dentro de `iaToolCall`, este teste fica
 * vermelho. Uma cópia do código nunca ficaria.
 *
 * O que está em causa
 * -------------------
 * Dois defeitos com a mesma assinatura: **o cliente dizia uma coisa e o
 * servidor fazia outra.**
 *
 *  1. A persona (`IA_SYSTEM`) ensinava 13 nomes de tool ao modelo. As 13 são
 *     fantasmas — nenhuma existe no catálogo. Toda a chamada que o modelo
 *     escrevia voltava `tool_fora_do_catalogo`. (FILA #27, P0.)
 *
 *  2. `iaToolCall` — marcada "DESLIGADA" em comentário desde o BUILD 0 — tinha
 *     dois POST vivos a `/api/iot/comandos/`, um POST a criar registos, um
 *     PATCH, um DELETE e um POST de relatório. E o ramo de irrigação mandava
 *     `device: lista[0]?.id || 1`. (FILA #32.)
 *
 * A regra que os dois fixes vêm tornar verdadeira, e que é o que se testa:
 *
 *   > o que o modelo aprende vem do servidor, e nada escreve por fora do
 *   > caminho auditado.
 *
 * NOTA SOBRE O CACHE
 * ------------------
 * `vocabularioAmplia()` tem cache de 10 minutos em módulo, que é o
 * comportamento certo em produção. Em teste, isso faz o teste anterior
 * lingerar no seguinte: o segundo teste pede uma falha de rede e recebe o
 * texto de cache do primeiro.
 *
 * A correcção é `vi.resetModules()` e um import dinâmico por teste, e não
 * uma função de reset no código de produção. Não se acrescenta superfície
 * ao que está em produção para acomodar quem testa — a não ser que o teste
 * esteja a verificar algo que só se vê com esse reset.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

/** O que o servidor devolve em `/api/amplia/vocabulario/`. */
const VOCABULARIO = {
  texto:
    'FERRAMENTAS DA AMPLIA — escreva o nome EXATAMENTE como esta aqui.\n\n' +
    'LEITURA (respondem sem perguntar nada):\n  clima: amplia_clima_agora, amplia_vai_chover\n' +
    'ESCRITA (mudam dados):\n  iot: amplia_ligar_irrigador, amplia_desligar_irrigador',
  cabe: true,
  chars: 240,
  total: 4,
};

/**
 * A única escrita permitida é a PORTA GOVERNADA.
 *
 * `/api/amplia/exec/` é um POST, e é o POST certo: é ele que vai a
 * `sandbox.executar`, que pede confirmação ao produtor e deixa linha em
 * `IAExecucao`. Contá-lo como escrita proibida seria proibir a solução.
 *
 * O que a lista abaixo diz é o resto: as leituras que usam POST por
 * transporte, e nenhum outro destino de escrita. É o que separa "a acção foi
 * pedida por um caminho auditado" de "a acção foi pedida por um caminho".
 */
const POSTS_QUE_SAO_LEITURA = ['/api/ia/web-search/'];

/** O destino de escrita único, e o único que passa por `sandbox.executar`. */
const PORTA_GOVERNADA = '/api/amplia/exec/';

function ehLeitura(c) {
  if (c.url.includes(PORTA_GOVERNADA)) return true;
  if (!['POST', 'PATCH', 'DELETE', 'PUT'].includes(c.metodo)) return true;
  return POSTS_QUE_SAO_LEITURA.some((p) => c.url.includes(p));
}

let chamadas = [];

/** Instala um `fetch` que regista tudo e responde pelo mapa. */
function instalarFetch(mapa) {
  global.fetch = vi.fn(async (url, opts = {}) => {
    const metodo = (opts.method || 'GET').toUpperCase();
    chamadas.push({ url: String(url), metodo, corpo: opts.body || null });
    const chave = `${metodo} ${url}`;
    const r = mapa[chave] ?? mapa[String(url)];
    if (r === undefined) throw new Error(`sem mock para ${chave}`);
    if (r instanceof Error) throw r;
    if (typeof r === 'function') return r(String(url), opts);
    return {
      ok: r.ok !== false,
      status: r.status || 200,
      json: async () => r,
      text: async () => JSON.stringify(r),
    };
  });
}

/** Um módulo novo a cada teste, para o cache não vazar de um para o outro. */
async function modulo() {
  vi.resetModules();
  return import('../../app/static/js/ia-local/ia-local.js');
}

beforeEach(() => {
  chamadas = [];
  global.fetch = vi.fn();
  document.cookie = 'csrftoken=teste; path=/';
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('o vocabulário que o modelo recebe', () => {
  it('vai ao servidor, e não a uma lista escrita à mão', async () => {
    instalarFetch({ '/api/amplia/vocabulario/': VOCABULARIO });
    const { vocabularioAmplia } = await modulo();

    const v = await vocabularioAmplia();

    expect(v).toBe(VOCABULARIO.texto);
    expect(chamadas.map((c) => c.url)).toContain('/api/amplia/vocabulario/');
  });

  it('devolve null quando o servidor não responde, e não inventa nomes', async () => {
    instalarFetch({ '/api/amplia/vocabulario/': new Error('rede') });
    const { vocabularioAmplia } = await modulo();

    // O ponto inteiro: `null` é uma resposta válida, e é o que faz o prompt
    // dizer "não há ferramentas agora" em vez de listar nomes inventados.
    expect(await vocabularioAmplia()).toBeNull();
  });

  it('não volta a buscar dentro do TTL', async () => {
    instalarFetch({ '/api/amplia/vocabulario/': VOCABULARIO });
    const { vocabularioAmplia } = await modulo();

    await vocabularioAmplia();
    const quantas = chamadas.length;
    await vocabularioAmplia();

    expect(chamadas.length).toBe(quantas);
  });

  it('leva o texto com o prefixo `amplia_`, como se escreve', async () => {
    instalarFetch({ '/api/amplia/vocabulario/': VOCABULARIO });
    const { vocabularioAmplia } = await modulo();

    expect(await vocabularioAmplia()).toContain('amplia_clima_agora');
  });
});

describe('iaToolCall não escreve nada', () => {
  const json = (tool, args = {}) => JSON.stringify({ tool, args });

  it('irrigação vai pela porta governada, não por POST directo', async () => {
    instalarFetch({
      '/api/amplia/exec/': { ok: true, resposta: 'Você confirma?', needs_confirm: true },
    });
    const { iaToolCall } = await modulo();

    const r = await iaToolCall(json('irrigacao', { acao: 'ligar', talhao: 'Talhão 3' }));

    // O que NÃO pode acontecer: um POST a /api/iot/comandos/.
    expect(chamadas.filter((c) => c.url.includes('/api/iot/comandos/'))).toEqual([]);

    // E o que tem de acontecer: passar por /api/amplia/exec/, que é o
    // caminho que pede confirmação e deixa linha em IAExecucao.
    const viaGov = chamadas.filter((c) => c.url.includes('/api/amplia/exec/'));
    expect(viaGov).toHaveLength(1);
    expect(JSON.parse(viaGov[0].corpo).tool).toBe('amplia_ligar_irrigador');
    expect(r).toBeTruthy();
  });

  it('"desligar" e "ligar" são acções diferentes e ficam separadas', async () => {
    instalarFetch({ '/api/amplia/exec/': { ok: true, resposta: 'Você confirma?' } });
    const { iaToolCall } = await modulo();

    await iaToolCall(json('irrigacao', { acao: 'desligar' }));

    const corpo = JSON.parse(chamadas.find((c) => c.url.includes('/api/amplia/exec/')).corpo);
    expect(corpo.tool).toBe('amplia_desligar_irrigador');
  });

  it('o talhão viaja nos argumentos, e não no texto', async () => {
    instalarFetch({ '/api/amplia/exec/': { ok: true, resposta: 'ok' } });
    const { iaToolCall } = await modulo();

    await iaToolCall(json('irrigacao', { acao: 'ligar', talhao: 'Talhão 3' }));

    const viaGov = chamadas.find((c) => c.url.includes('/api/amplia/exec/'));
    expect(JSON.parse(viaGov.corpo).args).toEqual({ talhao: 'Talhão 3' });
  });

  it('uma acção desconhecida recusa em vez de escolher uma', async () => {
    instalarFetch({ '/api/amplia/exec/': { ok: true } });
    const { iaToolCall } = await modulo();

    const r = await iaToolCall(json('irrigacao', { acao: 'explodir' }));

    expect(String(r)).toMatch(/só sei ligar ou desligar/i);
    expect(chamadas.filter((c) => c.url.includes('/api/amplia/exec/'))).toEqual([]);
  });

  it.each([
    ['criar', { recurso: 'safras', dados: { nome: 'x' } }],
    ['atualizar', { recurso: 'safras', id: 1, dados: { nome: 'y' } }],
    ['excluir', { recurso: 'safras', id: 1 }],
    ['deletar', { recurso: 'safras', id: 1 }],
    ['criar_operacao', { titulo: 'z' }],
  ])('%s não escreve por fora do sandbox', async (tool, args) => {
    instalarFetch({
      '/api/amplia/vocabulario/': VOCABULARIO,
      '/api/amplia/exec/': { ok: true },
    });
    const { iaToolCall } = await modulo();

    const r = await iaToolCall(json(tool, args));

    // Recusa com caminho, e não um "não consegui". O produtor precisa de
    // saber o que fazer a seguir.
    expect(String(r).length).toBeGreaterThan(10);
    expect(chamadas.filter((c) => !ehLeitura(c))).toEqual([]);
  });

  it('nenhum ramo escreve, nem toca em IoT', async () => {
    // Varredura por nome de tool: um ramo que escreva aparece aqui, seja
    // qual for. É a rede que pega o que os testes individuais não pensaram.
    const ramos = [
      'irrigacao',
      'criar',
      'atualizar',
      'excluir',
      'deletar',
      'criar_operacao',
      'relatorio',
      'gerar_relatorio',
      'buscar_web',
      'buscar_web_agro',
      'navegar',
      'abrir_pagina',
      'consultar',
      'buscar_dados',
      'ler_dados',
      'iniciar_cadastro',
      'cancelar_cadastro',
    ];

    for (const tool of ramos) {
      chamadas = [];
      instalarFetch({
        '/api/amplia/vocabulario/': VOCABULARIO,
        '/api/amplia/exec/': { ok: true, resposta: 'ok' },
        '/api/ia/web-search/': { snippets: [] },
        '/api/safras/': { results: [] },
        '/api/safras/1/': { ok: true },
        '/api/relatorio/gerar/': { ok: true },
        '/api/iot/devices/': { results: [] },
        '/api/iot/comandos/': { ok: true },
      });
      // Módulo novo por ramo: o cache do vocabulário é de 10 min e
      // transportava-se de um ramo para o seguinte.
      const { iaToolCall } = await modulo();

      try {
        await iaToolCall(json(tool, { recurso: 'safras', id: 1, q: 'x', destino: 'safras' }));
      } catch {
        /* o mock é escasso de propósito: interessa o que foi PEDIDO */
      }

      const escritas = chamadas.filter((c) => !ehLeitura(c));
      const iot = chamadas.filter((c) => c.url.includes('/api/iot/'));
      expect({ tool, escritas, iot }).toEqual({ tool, escritas: [], iot: [] });
    }
  });
});
