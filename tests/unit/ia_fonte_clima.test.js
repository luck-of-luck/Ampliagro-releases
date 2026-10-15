/**
 * A pergunta "(a) cadastrar estação?" — a que morria a meio.
 *
 * O QUE ESTE TESTE TRAVA
 * ----------------------
 * Três defeitos da mesma conversa, que apareceram juntos. Um produtor
 * perguntou "vai chover hoje", respondeu às três opções com "b", "c", "a",
 * e a cada resposta o sistema perdeu o fio:
 *
 *   1. (a) imprimia "Nome da estação?" mas NÃO abria o cadastro. A pessoa
 *      respondeu "estaçao met do lucas", e essa frase não é reconhecível
 *      como campo de nada — não havia máquina de estado à espera dela. O
 *      sistema respondeu "Entendi sua mensagem", que é a resposta honesta a
 *      uma frase que ele nunca tinha pedido nada. A pergunta certaina.
 *
 *   2. (b) respondia "Não consegui acessar os dados de clima. Verifique a
 *      estação meteorológica." O servidor tinha dito PORQUÊ — um 503 com
 *      "cadastre a cidade/UF da propriedade". O `.catch(() => null)`
 *      deitava essa frase fora, e no lugar dela punha-se a estação
 *      meteorológica, que ninguém pediu para verificar e que não era a
 *      causa. Uma falha sem motivo declarado não pode virar uma instrução
 *      inventada.
 *
 *   3. (c) despejava o `detail` do DRF no produtor: "Não consegui
 *      consultar os sensores: As credenciais de autenticação não foram
 *      fornecidas." A sessão tinha expirado — o `apiFetch` já sabe disso e
 *      já manda para o login. Falar a língua do servidor com quem não a
 *      entende, e sugerir um problema de conta que não existe.
 *
 * POR QUE UM TESTE DE COMPORTAMENTO, E NÃO DE ESTRUTURA
 * ------------------------------------------------------
 * Os testes de `clima_honesto.test.js` e `ia_comunicacao.test.js` extraem
 * o pedaço do ficheiro e correm-no. Aqui o mesmo: extrai-se a função de
 * decisão e a de normalização, e exercita-se o que o produtor LÊ. Um teste
 * que comparasse o texto do ficheiro passaria com a frase errada no sítio
 * certo, e rebentaria com a frase certa.
 */

import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';

const JS = path.resolve(__dirname, '../../app/static/js/ia-local/ia-local.js');
const fonte = fs.readFileSync(JS, 'utf-8');

/**
 * Recorta `function <nome>…` do ficheiro até a chaveta que fecha o corpo.
 *
 * O `async` é procurado À FRENTE, e não depois: `indexOf('function
 * buscarClimaWeb(')` casa dentro de `async function buscarClimaWeb(` e
 * devolve o texto a partir de `function` — deixando o `await` do corpo sem
 * função onde estar. O erro que daí sai ("await is only valid in async
 * functions") não tem nada a ver com o defeito que o teste quer apanhar,
 * e desvia para o ficheiro errado. É o mesmo desvio que o
 * `ia_cadastro_sem_recurso.test.js` descreve ao não extrair a função
 * inteira.
 */
function extrairFuncao(nome) {
  const marco = `function ${nome}(`;
  let inicio = fonte.indexOf(marco);
  if (inicio === -1) throw new Error(`${nome} não existe em ia-local.js`);
  // Só recua para o `async` se for mesmo o `async` desta função, e não o de
  // outra declaration qualquer que esteja encostada.
  if (fonte.slice(Math.max(0, inicio - 6), inicio) === 'async ') inicio -= 6;
  const abre = fonte.indexOf('{', inicio);
  let nivel = 0;
  for (let i = abre; i < fonte.length; i += 1) {
    if (fonte[i] === '{') nivel += 1;
    else if (fonte[i] === '}') {
      nivel -= 1;
      if (nivel === 0) return fonte.slice(inicio, i + 1);
    }
  }
  throw new Error(`não consegui fechar ${nome}`);
}

/** Corre `normalizarPrevisaoClima` isoladamente. */
function normalizar(payload) {
  const fn = new Function(
    `${extrairFuncao('normalizarPrevisaoClima')}; return normalizarPrevisaoClima;`
  )();
  return fn(payload);
}

/**
 * Corre `buscarClimaWeb` com um `apiFetch` falso.
 *
 * Devolve a resposta final a partir de um mapa de endpoints, para se poder
 * reproduzir cada uma das falhas que o produtor viu.
 */
async function buscarClima({ previsaoClima, weather }) {
  const mapa = JSON.stringify({ previsao: previsaoClima ?? null, weather: weather ?? null });
  const corpo = `
    ${extrairFuncao('normalizarPrevisaoClima')}
    function formatarDadosNatural(recurso, data) {
      if (recurso === 'clima' && data && data.__semDados) return data.__semDados;
      return 'PREVISAO_MOCK';
    }
    async function apiFetch(url) {
      const mapa = ${mapa};
      const spec = url.indexOf('previsao-clima') !== -1 ? mapa.previsao : mapa.weather;
      if (spec === null) throw Object.assign(new Error('sem rota'), { status: 404 });
      if (spec.erro) {
        const e = new Error(spec.erro);
        e.status = spec.status || 500;
        if (spec.semSessao) e.semSessao = true;
        throw e;
      }
      return spec.dados;
    }
    ${extrairFuncao('buscarClimaWeb')}
  `;
  const fn = new Function(`${corpo}; return buscarClimaWeb;`)();
  return fn();
}

/** A forma real de `/api/previsao-clima/` — o dialeto do Open-Meteo. */
const OPEN_METEO = {
  latitude: -21.39,
  longitude: -46.47,
  timezone: 'America/Sao_Paulo',
  fonte: 'georef:talhao:Fazenda Norte',
  daily: {
    time: ['2026-10-10', '2026-10-11', '2026-10-12'],
    temperature_2m_max: [29.4, 24.1, 22.0],
    temperature_2m_min: [17.2, 16.9, 15.8],
    precipitation_sum: [0.0, 12.4, 30.1],
    precipitation_probability_max: [5, 70, 85],
  },
};

describe('(b) a previsão pela internet', () => {
  it('lê a previsão de 7 dias que o /api/previsao-clima/ devolve', () => {
    // O payload do Open-Meteo tem `daily`, e o formatador lia `atual`. Sem
    // esta normalização, o produtor recebia "não encontrei dados" com sete
    // dias completos à espera — e a culpa era do produtor por perguntar.
    const n = normalizar(OPEN_METEO);
    expect(n.previsao).toHaveLength(3);
    expect(n.atual.temp).toBeCloseTo((29.4 + 17.2) / 2, 1);
  });

  it('nunca transforma "a fonte não disse" em 0', () => {
    // `null` é ausência; 0 é um número. Trocá-los fabrica uma medição.
    const semNada = normalizar({ daily: { time: ['2026-10-10'] } });
    expect(semNada.atual.temp).toBeNull();
  });

  it('não mexe num payload que já vem na forma comum', () => {
    const jaNormalizado = { fonte: 'inmet', atual: { temp: 26 }, previsao: [] };
    expect(normalizar(jaNormalizado)).toBe(jaNormalizado);
  });

  it('DIZ O MOTIVO do servidor, em vez de culpar a estação', async () => {
    // Este é o defeito real. O 503 traz o motivo escrito para o caso
    // concreto; deitá-lo fora e dizer "verifique a estação" é inventar um
    // culpado — e mandar a pessoa comprar uma estação que não é o problema.
    const r = await buscarClima({
      previsaoClima: {
        status: 503,
        erro: 'cadastre a cidade/UF da propriedade, uma estação, ou o GPS',
      },
      weather: { status: 503, erro: 'sem coordenada' },
    });
    expect(r).toContain('cadastre a cidade/UF');
  });

  it('NUNCA manda verificar a estação quando o problema é a coordenada', async () => {
    const r = await buscarClima({
      previsaoClima: { status: 503, erro: 'cadastre a cidade/UF da propriedade' },
      weather: { status: 503, erro: 'sem coordenada' },
    });
    expect(r).not.toMatch(/Verifique a estação/i);
  });

  it('diz o que fazer, porque um "não sei" sem saída é um beco', async () => {
    const r = await buscarClima({
      previsaoClima: { status: 503, erro: 'cadastre a cidade/UF' },
      weather: { status: 503, erro: 'sem coordenada' },
    });
    expect(r).toMatch(/cidade\/UF/i);
  });

  it('trata a sessão expirada como sessão — não como "sem rota"', async () => {
    const r = await buscarClima({
      previsaoClima: { status: 401, erro: 'não autenticado', semSessao: true },
      weather: { status: 401, erro: 'não autenticado', semSessao: true },
    });
    expect(r).toMatch(/sessão/i);
  });

  it('não inventa temperatura quando nenhum endpoint respondeu', async () => {
    const r = await buscarClima({
      previsaoClima: { status: 500, erro: 'erro interno' },
      weather: { status: 500, erro: 'erro interno' },
    });
    expect(r).not.toMatch(/\d+\s*°C/);
  });
});

describe('(c) os sensores', () => {
  /** Corre o ramo `sensores` do formatador com o payload real da view. */
  function formatarSensores(data) {
    const inicio = fonte.indexOf("if (recurso === 'sensores') {");
    if (inicio === -1) throw new Error('o ramo dos sensores não existe mais');
    const abre = fonte.indexOf('{', inicio);
    let nivel = 0;
    let fim = -1;
    for (let i = abre; i < fonte.length; i += 1) {
      if (fonte[i] === '{') nivel += 1;
      else if (fonte[i] === '}') {
        nivel -= 1;
        if (nivel === 0) {
          fim = i + 1;
          break;
        }
      }
    }
    const corpo = `
      function fmtNum(v, dec = 2) { return v == null ? '—' : String(v); }
      function formatarDadosNatural(recurso, data) {
        const items = data?.results || (Array.isArray(data) ? data : null);
        const count = data?.count ?? items?.length ?? 0;
        ${fonte.slice(inicio, fim)}
        return '(sem ramo)';
      }
    `;
    const fn = new Function(`${corpo}; return formatarDadosNatural;`)();
    return fn('sensores', data);
  }

  it('DIZ O NOME dos sensores, não só quantos há', () => {
    // A forma real de `sensores_data`. O ramo antigo varria números do topo
    // e `total` é o único — respondia "📡 Sensores: total: 2" a uma pessoa
    // que perguntou QUE sensores tem. A pergunta respondida com o número.
    const r = formatarSensores({
      sensores: [
        { nome: 'Estação do Lucas', propriedade: 'Fazenda Norte', ativa: true },
        { nome: 'Estação do Portão', propriedade: 'Fazenda Norte', ativa: true },
      ],
      total: 2,
    });
    expect(r).toContain('Estação do Lucas');
    expect(r).toContain('Estação do Portão');
  });

  it('marca a estação inativa, porque uma estação desligada não mede', () => {
    const r = formatarSensores({
      sensores: [{ nome: 'Estação Velha', propriedade: 'Fazenda Norte', ativa: false }],
      total: 1,
    });
    expect(r).toMatch(/inativa/i);
  });

  it('o zero é CONTADO, e mesmo assim diz o que fazer', () => {
    // "0 sensores" sem saída é um beco, e (c) é pedido logo depois de
    // alguém ouvir que não tem estação. Um beco aqui acaba com o clima.
    const r = formatarSensores({ sensores: [], total: 0 });
    expect(r).toMatch(/não tem sensores/i);
    expect(r).toMatch(/cadastrar/i);
  });

  it('não diz "não tem sensores" quando o total não veio', () => {
    // Um total ausente é "não perguntámos". Dizer "não tem" é afirmar um
    // facto que ninguém mediu.
    const r = formatarSensores({});
    expect(r).not.toMatch(/não tem sensores/i);
  });

  it('`sensores` está no dicionário de recursos', () => {
    // Estava ausente: o chamador usava `RECURSOS_API['sensores'] || '/api/sensores/'`.
    // O `||` salvava a chamada, mas o nome ficava fora do mapa que todos os
    // outros caminhos usam — e um literal envelhece sozinho.
    expect(/sensores:\s*'\/api\/sensores\/'/.test(fonte)).toBe(true);
  });

  it('não despeja o "detail" do DRF no produtor', () => {
    // "As credenciais de autenticação não foram fornecidas" fala a língua
    // do servidor com quem não a entende, e sugere um problema de conta que
    // não existe. A sessão expirou; é isso que se diz.
    expect(fonte).not.toMatch(/Não consegui consultar os sensores: \$\{e\.message\}/);
  });
});

describe('(a) o cadastro da estação', () => {
  /** Recorta o `if (intent.tipo === 'criar' …)` que abre o cadastro. */
  function extrairGuardaCriar() {
    const inicio = fonte.indexOf("if (intent.tipo === 'criar'");
    if (inicio === -1) throw new Error('guarda de `criar` não encontrada');
    const abre = fonte.indexOf('{', inicio);
    let nivel = 0;
    for (let i = abre; i < fonte.length; i += 1) {
      if (fonte[i] === '{') nivel += 1;
      else if (fonte[i] === '}') {
        nivel -= 1;
        if (nivel === 0) return fonte.slice(inicio, i + 1);
      }
    }
    throw new Error('não consegui fechar o guarda de `criar`');
  }

  // Envolve o guarda numa função com os nomes que ele usa.
  //
  // O `()` no fim é o que a constrói: `new Function(corpo)` devolve a função
  // que EXECUTA o corpo, e é essa que se chama aqui. Sem ele, `COM_GUARDA`
  // seria a fábrica — e chamar a fábrica devolveria o código-fonte da
  // função, que é o que o teste via.
  //
  // O esquema tem de trazer `obrigatorio`, e não um `{campo:'nome'}` pelado:
  // o guarda decide por `ESQUEMAS_CADASTRO[intent.acao]` existir, e um
  // esquema inventado que não bate com o real deixa o teste a verificar um
  // dicionário que ninguém maintaine — o mesmo erro que o
  // `ia_cadastro_sem_recurso.test.js` descreve ao escrever as nove chaves à
  // mão.
  const COM_GUARDA = new Function(
    `
    const ESQUEMAS_CADASTRO = {
      estacoes: [{ campo: 'nome', obrigatorio: true }],
      safras: [{ campo: 'nome', obrigatorio: true }],
    };
    function iniciarCadastro(recurso) { return 'ABRIU:' + recurso; }
    function _dec(d, t) { return d + '|' + t; }
    function _guarda(intent, iaCadastroPendente) {
      ${extrairGuardaCriar()}
      return null;
    }
    return _guarda;
    `
  )();

  function decidir(intent, pendente) {
    return COM_GUARDA(intent, pendente);
  }

  const CRIAR_ESTACAO = {
    tipo: 'criar',
    acao: 'estacoes',
    falta: ['nome', 'latitude', 'longitude'],
  };

  it('ABRE o cadastro, e não se limita a imprimir a pergunta', () => {
    // O defeito. `iniciarCadastro` é o que põe `iaCadastroPendente` de pé;
    // sem ele, a resposta seguinte não tem onde cair.
    const r = decidir(CRIAR_ESTACAO, null);
    expect(String(r)).toContain('ABRIU:estacoes');
  });

  it('o guarda vem ANTES do `if` de `falta`, que de outro modo o consome', () => {
    // `falta` preenchida fazia o bloco anterior devolver a STRING da
    // pergunta e seguir. Se o guarda viesse depois, `criar` nunca chegava
    // aqui — e a correcção seria inerte.
    const posGuarda = fonte.indexOf("if (intent.tipo === 'criar'");
    const posFalta = fonte.indexOf('if (intent.falta && intent.falta.length > 0');
    expect(posGuarda).toBeGreaterThan(-1);
    expect(posFalta).toBeGreaterThan(-1);
    expect(posGuarda).toBeLessThan(posFalta);
  });

  it('não abre um cadastro por cima de outro em curso', () => {
    // Quem está a meio de um cadastro tem direito a acabar ou a cancelar.
    const r = decidir(CRIAR_ESTACAO, { recurso: 'safras', etapa: 1, esquema: [{}, {}] });
    expect(String(r)).not.toContain('ABRIU:');
    expect(String(r)).toMatch(/cancelar/i);
  });

  it('qualquer recurso com esquema abre o seu cadastro', () => {
    // A correcção não é um remendo para a estação: `criar` é o mesmo tipo
    // de intenção para todos os recursos, e o mesmo defeito.
    expect(String(decidir({ tipo: 'criar', acao: 'safras', falta: ['nome'] }, null))).toContain(
      'ABRIU:safras'
    );
  });

  it('o esquema da estação pede nome, e o nome existe como campo', () => {
    // Se `ESQUEMAS_CADASTRO.estacoes` não existisse, `iniciarCadastro`
    // devolveria "ainda não tem wizard" e a conversa morria outra vez — com
    // uma mensagem diferente e o mesmo efeito.
    const ini = fonte.indexOf('estacoes: [');
    expect(ini).toBeGreaterThan(-1);
    const trecho = fonte.slice(ini, ini + 900);
    expect(trecho).toMatch(/campo:\s*'nome'/);
    expect(trecho).toMatch(/obrigatorio:\s*true/);
  });
});
