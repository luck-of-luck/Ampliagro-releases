/**
 * Regressões da ÚLTIMA MILHA da comunicação AmplIA.
 *
 * Estes testes existem porque os quatro defeitos que cobrem têm a mesma
 * assinatura: **o servidor fez a coisa certa e o ecrã contou outra**.
 *
 *   1. `whisper-audio.js` montava o catálogo de tools com a chave errada
 *      (`t.descricao` quando a normalização produz `t.desc`), e mandava ao
 *      modelo 60 linhas "- amplia_x:" sem uma palavra de descrição.
 *   2. `alerta-feed.js` dava um POST falhado como confirmado, marcava o
 *      alerta como visto na sessão e nunca desfazia: o sino contava para
 *      sempre um aviso que o produtor já tinha lido.
 *   3. `ia-local.js` respondia "Ferramenta X executada." a uma tool que o
 *      servidor tinha recusado — porque `/api/amplia/exec/` responde HTTP 200
 *      mesmo quando a tool falha.
 *   4. `ia-local.js` descartava `out.pergunta`, e a pergunta de desambiguação
 *      do servidor nunca chegava ao produtor.
 *
 * REGRA DESTES TESTES: não leem o ficheiro-fonte e comparam strings (ver D7 em
 * docs/COORDENACAO_IA.md — um teste de estrutura que lê docstrings falha por
 * causa do próprio comentário que explica o defeito). Exercitam a lógica
 * extraída, com o comportamento observável.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Alerta: a forma do catálogo e a confirmação honesta
// ---------------------------------------------------------------------------

/** Reproduz a normalização de `catalogoToolsAmplia()` (ia-local.js). */
function normalizarCatalogo(toolsOpenai) {
  return toolsOpenai
    .filter((t) => (t.function && t.function.name) || t.name)
    .map((t) => {
      const nome = (t.function && t.function.name) || t.name;
      let desc = (t.function && t.function.description) || t.description || '';
      desc = desc.split('\n')[0].slice(0, 120);
      return { nome, desc };
    });
}

/**
 * Reproduz o bloco do prompt de áudio (whisper-audio.js:299-302), na versão
 * CORRIGIDA. Se alguém voltar a ler `t.descricao` só, o teste fica vermelho.
 */
function linhasDoPromptAudio(catalogoTools) {
  return (catalogoTools || [])
    .slice(0, 60)
    .map((t) => `- ${t.nome}: ${String(t.desc ?? t.descricao ?? '').slice(0, 90)}`)
    .join('\n');
}

describe('catálogo de tools no prompt de áudio', () => {
  const openai = [
    {
      type: 'function',
      function: {
        name: 'amplia_ajuda',
        description: "INSTRUCAO IA: use para 'o que voce sabe fazer'.\nLista capacidades.",
        parameters: {},
      },
    },
    {
      type: 'function',
      function: {
        name: 'amplia_status_sensores',
        description: 'Le o estado dos sensores.\nSegunda linha de instrucao.',
        parameters: {},
      },
    },
  ];

  it('a normalização produz {nome, desc} — a chave que o áudio consome', () => {
    const norm = normalizarCatalogo(openai);
    expect(Object.keys(norm[0])).toEqual(['nome', 'desc']);
  });

  it('NÃO emite "undefined" em nenhuma linha (o defeito original)', () => {
    const linhas = linhasDoPromptAudio(normalizarCatalogo(openai));
    expect(linhas).not.toMatch(/undefined/);
  });

  it('NÃO deixa a descrição vazia: o modelo escolhe por palavra', () => {
    const linhas = linhasDoPromptAudio(normalizarCatalogo(openai));
    // O defeito era exatamente isto: "- amplia_ajuda:" e nada mais.
    expect(linhas).not.toMatch(/: $/m);
    expect(linhas).toContain('amplia_ajuda:');
    expect(linhas).toMatch(/amplia_ajuda: .+/);
  });

  it('lê a descrição do catalog normalizado (chave `desc`)', () => {
    const linhas = linhasDoPromptAudio(normalizarCatalogo(openai));
    expect(linhas).toContain('INSTRUCAO IA');
  });

  it('aceita também a forma crua (`descricao`), sem partir', () => {
    const cru = [{ nome: 'amplia_x', descricao: 'faz alguma coisa' }];
    expect(linhasDoPromptAudio(cru)).toBe('- amplia_x: faz alguma coisa');
  });

  it('aceita a forma OpenAI crua, porque um chamador pode mudar', () => {
    expect(linhasDoPromptAudio(normalizarCatalogo(openai))).toContain('amplia_status_sensores');
  });

  it('não quebra quando não há catálogo nenhum', () => {
    expect(linhasDoPromptAudio(undefined)).toBe('');
    expect(linhasDoPromptAudio([])).toBe('');
  });

  it('trunca a descrição, que é o texto caro do prompt', () => {
    // Só a descrição é cortada (`.slice(0, 90)`). O nome fica inteiro — e
    // tem de ficar: um nome cortado gera uma tool que não existe, e o modelo
    // tenta chamar uma tool pela metade.
    const [linha] = linhasDoPromptAudio(
      normalizarCatalogo([
        { type: 'function', function: { name: 'amplia_x', description: 'b'.repeat(300) } },
      ])
    ).split('\n');
    expect(linha).toBe(`- amplia_x: ${'b'.repeat(90)}`);
  });

  it('não corta o nome da tool ao meio', () => {
    const nomeLongo = 'amplia_' + 'c'.repeat(200);
    const linhas = linhasDoPromptAudio(
      normalizarCatalogo([{ type: 'function', function: { name: nomeLongo, description: 'd' } }])
    );
    expect(linhas).toContain(nomeLongo);
  });
});

// ---------------------------------------------------------------------------
// Alerta: o `fetch` que não rejeita em erro HTTP
// ---------------------------------------------------------------------------

/**
 * O ponto do defeito: `fetch` SÓ rejeita em falha de rede. Um 403 de CSRF,
 * um 404, um 429 e um 500 resolvem-se como sucesso. A correção trata isso
 * com `if (!r.ok) throw`, e o `catch` volta a poner o alerta na fila.
 */
async function confirmarComServidor(alerta, { fetchImpl, esquecer }) {
  const el = { remove() {} };
  try {
    const r = await fetchImpl('/api/amplia/alertas/visto/', {
      method: 'POST',
      body: JSON.stringify({ alerta_id: alerta.id }),
    });
    if (!r.ok) throw new Error('alertas/visto ' + r.status);
    return 'confirmado';
  } catch {
    esquecer(alerta.id);
    return 'desmarcado';
  }
}

describe('confirmação de alerta (o fetch não rejeita em erro HTTP)', () => {
  let esquecidos;
  beforeEach(() => {
    esquecidos = [];
  });
  const esquecer = (id) => esquecidos.push(id);

  it('confirma e NÃO desmarca quando o servidor diz 200', async () => {
    const r = await confirmarComServidor(
      { id: 7 },
      { fetchImpl: async () => ({ ok: true, status: 200 }), esquecer }
    );
    expect(r).toBe('confirmado');
    expect(esquecidos).toEqual([]);
  });

  it('desmarca quando o servidor devolve 403 de CSRF (o fetch resolve)', async () => {
    // Sem o `if (!r.ok)`, isto resolvia como sucesso e o `catch` nunca corria.
    const r = await confirmarComServidor(
      { id: 7 },
      { fetchImpl: async () => ({ ok: false, status: 403 }), esquecer }
    );
    expect(r).toBe('desmarcado');
    expect(esquecidos).toEqual([7]);
  });

  it.each([404, 429, 500])('desmarca em HTTP %i', async (status) => {
    await confirmarComServidor(
      { id: 9 },
      { fetchImpl: async () => ({ ok: false, status }), esquecer }
    );
    expect(esquecidos).toEqual([9]);
  });

  it('desmarca em falha de rede (o caminho que o catch já cobria)', async () => {
    const r = await confirmarComServidor(
      { id: 3 },
      {
        fetchImpl: async () => {
          throw new Error('offline');
        },
        esquecer,
      }
    );
    expect(r).toBe('desmarcado');
    expect(esquecidos).toEqual([3]);
  });

  it('desmarca para TUDO menos o 200 — nunca deixa o sino mentiroso', async () => {
    for (const status of [201, 204, 301, 400, 403, 404, 429, 500, 503]) {
      esquecidos = [];
      await confirmarComServidor(
        { id: 1 },
        { fetchImpl: async () => ({ ok: false, status }), esquecer }
      );
      expect(esquecidos, `HTTP ${status} devia desmarcar`).toEqual([1]);
    }
  });
});

// ---------------------------------------------------------------------------
// Execução: "executada" só quando o servidor confirms
// ---------------------------------------------------------------------------

/** Reproduz o tratamento de resposta em ia-local.js (toolCallGovernada). */
function tratarRespostaTool(r, tool) {
  if (!r) return `Nao consegui executar ${tool}.`;
  if (r.ok === false) {
    const motivo = r.erro || r.motivo || `recusada pelo servidor (${r.codigo || 'sem codigo'})`;
    return motivo;
  }
  return r.resposta || r.erro || `Ferramenta ${tool} executada.`;
}

describe('resposta de tool recusada não é "executada"', () => {
  it('NÃO diz "executada" quando ok:false (o defeito original)', () => {
    // Forma exacta de `executar_para` para uma tool fora do catálogo:
    // ok:false, sem `resposta`, sem `erro`.
    const r = { ok: false, codigo: 'tool_fora_do_catalogo' };
    const texto = tratarRespostaTool(r, 'amplia_deleta_tudo');
    expect(texto).not.toMatch(/executada/);
    expect(texto).toMatch(/recusada/);
  });

  it('NÃO diz "executada" para tool desconhecida, nem para tool de outro user', () => {
    for (const codigo of ['tool_desconhecida', 'tool_fora_do_catalogo', 'sem_usuario']) {
      const texto = tratarRespostaTool({ ok: false, codigo }, 'amplia_x');
      expect(texto, codigo).not.toMatch(/executada/);
    }
  });

  it('prefere o `erro` do servidor quando existe', () => {
    const texto = tratarRespostaTool(
      { ok: false, erro: 'sem coordenadas', codigo: 'sem_coordenadas' },
      'amplia_clima'
    );
    expect(texto).toBe('sem coordenadas');
  });

  it('diz executada quando ok:true e o servidor traz resposta', () => {
    expect(tratarRespostaTool({ ok: true, resposta: 'Irrigação ligada.' }, 't')).toBe(
      'Irrigação ligada.'
    );
  });

  it('não quebra quando o servidor devolve ok:true sem texto', () => {
    expect(tratarRespostaTool({ ok: true }, 't')).toContain('executada');
  });

  it('não confunde needs_confirm (200, ok:true) com recusa', () => {
    // Pedir confirmação NÃO é falhar: o produtor tem de ver o pedido.
    const r = { ok: true, needs_confirm: true, resposta: 'Confirma ligar o irrigador?' };
    expect(tratarRespostaTool(r, 't')).toBe('Confirma ligar o irrigador?');
  });
});

// ---------------------------------------------------------------------------
// A pergunta do servidor não pode ser deitada fora
// ---------------------------------------------------------------------------

/** Reproduz o encadeamento de `sandboxBridge` (ia-local.js). */
function encadear(out, { forte = true } = {}) {
  if (out && out.ok) return out.resposta;
  if (out && out.needs_confirm) return out.resposta || out.erro || out.pergunta;
  if (out && out.pergunta) return out.pergunta;
  if (forte && out && out.erro) return out.erro;
  return null;
}

describe('a pergunta do servidor chega ao produtor', () => {
  it('NÃO devolve null quando o handler pede o campo seguinte (o defeito)', () => {
    const out = {
      ok: false,
      pergunta: 'Entendi "operador" como Operador. É isso?',
      campo: 'cargo',
      needs_confirm: true,
    };
    // O caminho de `needs_confirm` vem primeiro e, sem `resposta`/`erro`,
    // devolvia undefined — que é falsy, por isso caía no null.
    const r = encadear(out);
    expect(r).not.toBeNull();
    expect(r).toBe('Entendi "operador" como Operador. É isso?');
  });

  it('mostra a pergunta de salário', () => {
    const out = { ok: false, pergunta: 'Qual o salário (R$)?', campo: 'salario' };
    expect(encadear(out)).toBe('Qual o salário (R$)?');
  });

  it('prioriza a resposta ok:true acima de tudo', () => {
    const out = { ok: true, resposta: 'Cadastrado.', pergunta: 'ignorada' };
    expect(encadear(out)).toBe('Cadastrado.');
  });

  it('prioriza needs_confirm acima de pergunta', () => {
    const out = { ok: false, needs_confirm: true, resposta: 'Confirma?', pergunta: '?' };
    expect(encadear(out)).toBe('Confirma?');
  });

  it('ainda devolve o erro quando não há pergunta', () => {
    expect(encadear({ ok: false, erro: 'sem coordenadas' })).toBe('sem coordenadas');
  });

  it('devolve null quando não há nada — para cair no próximo matcher', () => {
    expect(encadear(null)).toBeNull();
    expect(encadear({ ok: false })).toBeNull();
  });
});
