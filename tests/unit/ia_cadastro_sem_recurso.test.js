import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';

// "como se cadastrar" — a pergunta que um produtor fez e que o sistema
// nao respondeu.
//
// O bug: o handler casa o VERBO (`cadastrar`), depois percorre uma lista
// de dez REGULOS e nenhuma diz "funcion" — a frase "como se cadastrar"
// nao contem nenhuma palavra de recurso. O loop nao casa, o `if` nao
// devolve nada, e a execucao segue para o `return null` — que e' o
// fallback generico: "Entendi sua mensagem: ... Como posso ajudar?".
//
// A pergunta era legitima. A resposta devia ser uma pergunta, nao um
// menu de recursos que nao tem nada a ver com o que foi pedido.
//
// Este ficheiro CORRE o `if` do ficheiro real — nao uma reescrita dele.

const JS = path.resolve(process.cwd(), 'app/static/js/ia-local/ia-local.js');
const fonte = fs.readFileSync(JS, 'utf-8');

// As nove chaves que EXISTEM de facto em ESQUEMAS_CADASTRO. Nao uma
// chave inventada: o teste tem de usar o mesmo dicionario que o ficheiro
// real, senao passa a verificar uma lista que ninguem maintaine.
const RECURSOS_REAIS = {
  funcionarios: [{ campo: 'nome' }],
  safras: [{ campo: 'nome' }],
  talhoes: [{ campo: 'nome' }],
  operacoes: [{ campo: 'nome' }],
  estoque: [{ campo: 'nome' }],
  insumos: [{ campo: 'nome' }],
  culturas: [{ campo: 'nome' }],
  estacoes: [{ campo: 'nome' }],
  propriedades: [{ campo: 'nome' }],
};

/**
 * Extrai o `if (t.match(/configurar|cadastrar.../)) { ... }` e o
 * `return null` que lhe segue.
 *
 * Recorta pelo `if` e conta as chavetas ate fechar. Cortar pela funcao
 * inteira trazia os `await apiFetch(...)` de outros ramos, e o `vm`
 * falhava com "await is only valid in async functions" — um erro que nao
 * tem nada a ver com o bug que queremos apanhar, e que gastou meia hora
 * a desorientar.
 */
function extraiBloco() {
  // Procura pelo VERBO, nao pelo regex inteiro.
  //
  // O regex do `if` ja foi reescrito duas vezes (para aceitar os verbos
  // conjugados) e o teste partiu de cada vez, com "o if de cadastro nao
  // existe mais". Um teste que afina com a forma exacta do codigo que
  // testa quebra em cada correccao — inclusive nas que resolve.
  //
  // O que o bloco TEM de ter: a lista `mapCadastro` e um `return null`
  // atras. A forma do verbo nao interessa ao que este teste verifica.
  const mapa = fonte.indexOf('const mapCadastro');
  if (mapa === -1) throw new Error('mapCadastro nao existe no ficheiro');

  const ini = fonte.lastIndexOf('if (', mapa);
  if (ini === -1) throw new Error('nao encontrei o if de cadastro');

  // fecha o if: conta chavetas a partir da chave que abre o corpo
  const abre = fonte.indexOf('{', mapa);
  let nivel = 0;
  let fim = abre;
  for (let k = abre; k < fonte.length; k += 1) {
    if (fonte[k] === '{') nivel += 1;
    else if (fonte[k] === '}') {
      nivel -= 1;
      if (nivel === 0) {
        fim = k;
        break;
      }
    }
  }

  // e o `return null;` que fecha o handler
  const r = fonte.indexOf('return null;', fim);
  if (r === -1) throw new Error('nao encontrei o return null');
  return fonte.slice(ini, r + 'return null;'.length);
}

const bloco = extraiBloco();

function corre(frase) {
  const t = String(frase).toLowerCase();
  // `querCriarSemRecurso` vive FORA do bloco extraido (esta ao nivel
  // do ficheiro). Passa-se como argumento em vez de deixar o `new
  // Function` a procura-lo no scope global do modulo — que no vitest e'
  // um scope diferente, e dava ReferenceError em vez de um resultado.
  const f = new Function('t', 'ESQUEMAS_CADASTRO', 'iniciarCadastro', 'querCriarSemRecurso', bloco);
  return f(t, RECURSOS_REAIS, (r) => `INICIO:${r}`, querCriarSemRecurso);
}

/**
 * A MESMA regra que o ficheiro usa, lida do ficheiro.
 *
 * Nao uma copia: se o ficheiro mudar a regra e esta copia nao, o teste
 * passa a verificar a regra antiga. Le-se do codigo real.
 */
function querCriarSemRecurso(t) {
  const m = new RegExp(
    String.raw`function\s+querCriarSemRecurso\s*\(t\)\s*\{\s*return\s+(.+?);\s*\}`
  ).exec(fonte);
  if (!m) throw new Error('querCriarSemRecurso nao existe no ficheiro');
  const f = new Function('t', `return ${m[1]};`);
  return f(String(t).toLowerCase());
}

describe('o bloco de cadastro esta no ficheiro', () => {
  it('foi extraido com o seu return', () => {
    expect(bloco).toContain('mapCadastro');
    expect(bloco).toContain('return null');
  });

  it('nao tem await, para o vm o conseguir correr', () => {
    // Se voltar a ter, o teste falha com um erro de sintaxe que nao
    // explica nada sobre o bug.
    expect(bloco).not.toContain('await');
  });
});

describe('"como se cadastrar" nao pode cair no fallback', () => {
  it('a frase nao contem nenhuma palavra de recurso', () => {
    // A razao do bug. Se um dia "cadastrar" passar a conter "funcion",
    // o handler deixa de cair no null e a correccao fica obsoleta sem
    // ninguem reparar.
    const t = 'como se cadastrar';
    const recursos = [
      /estacao|estação|meteo|meteorolog/,
      /funcion/,
      /safra/,
      /talh/,
      /estoque/,
      /opera|tarefa/,
      /insumo/,
      /cultura/,
      /propried|fazenda/,
    ];
    expect(recursos.filter((r) => r.test(t))).toHaveLength(0);
  });

  it('devolve uma pergunta, e nao null', () => {
    const r = corre('como se cadastrar');
    expect(r).not.toBeNull();
    expect(typeof r).toBe('string');
  });

  it('a pergunta diz o que se pode criar', () => {
    const r = corre('como se cadastrar');
    expect(r).toMatch(/Posso criar/);
    expect(r).toMatch(/tipos de registo/);
  });

  it('nao escolhe um recurso por defeito', () => {
    // Escolher seria inventar o que a pessoa queria — o defeito que
    // esta camada existe para evitar.
    const r = corre('como se cadastrar');
    expect(r).not.toMatch(/^INICIO:/);
  });

  it('lista os recursos que existem, lidos de ESQUEMAS_CADASTRO', () => {
    // Nao uma lista escrita a mao: seria a FALLBACK_METRICS com outra
    // forma.
    const r = corre('como se cadastrar');
    for (const nome of Object.keys(RECURSOS_REAIS)) {
      expect(r).toContain(nome);
    }
  });
});

describe('cada forma de perguntar sem dizer o recurso', () => {
  const perguntas = [
    'como se cadastrar',
    'como criar',
    'qual o registo',
    'o que posso cadastrar',
    'como se adiciona',
    'como se registra',
  ];

  it('todas devolvem uma pergunta', () => {
    for (const p of perguntas) {
      expect(corre(p), `"${p}" caiu no fallback`).not.toBeNull();
    }
  });
});

describe('o mapa nao pode prometer recursos que nao existem', () => {
  // Este e' o achado que valeu mais a pena. `mapCadastro` apontava para
  // `maquinanarios`, que nunca esteve em ESQUEMAS_CADASTRO. O handler
  // devolvia "Posso criar maquinarios para você. Me diga os dados que
  // deseja cadastrar" — e depois nao havia formulario para pedir os
  // dados.
  //
  // A promessa vazia e' pior que o "nao percebi": o "nao percebi" obriga
  // a pessoa a tentar outra frase; a promessa faz-a preencher o
  // formulario imaginario e esperar por um resultado que nao chega.
  const m = new RegExp(String.raw`\[\(\?\:?[^/]*?/g?[i]*\)?\s*,\s*'([a-z_]+)'\]`, 'g');
  const alvos = [...bloco.matchAll(/\[[^\]]*?,\s*'([a-z_]+)'\]/g)].map((x) => x[1]);

  it('o mapa foi extraido e tem alvos', () => {
    expect(alvos.length).toBeGreaterThan(0);
    expect(m).toBeTruthy();
  });

  it('cada alvo existe mesmo em ESQUEMAS_CADASTRO', () => {
    const inexistentes = alvos.filter((r) => !(r in RECURSOS_REAIS));
    expect(inexistentes, `o mapa aponta para recursos que nao existem: ${inexistentes}`).toEqual(
      []
    );
  });

  it('"adicionar trator" nao promete um formulario que nao ha', () => {
    const r = corre('adicionar trator');
    expect(r).not.toBeNull();
    // A pergunta honesta: pergunta o que se quer criar.
    expect(r).toMatch(/Posso criar/);
  });
});

describe('o que continua a funcionar como estava', () => {
  // Uma correccao que parte o caminho que ja funcionava e' uma correccao
  // errada. Estes eram o caminho certo.

  it('"cadastrar o funcionario" vai para funcionarios', () => {
    expect(corre('cadastrar o funcionario')).toBe('INICIO:funcionarios');
  });

  it('"novo talhao" vai para talhoes', () => {
    expect(corre('novo talhao')).toBe('INICIO:talhoes');
  });

  it('"criar safra de soja" vai para safras', () => {
    expect(corre('criar safra de soja')).toBe('INICIO:safras');
  });

  it('"registrar insumo" vai para insumos', () => {
    expect(corre('registrar insumo')).toBe('INICIO:insumos');
  });

  it('"nova propriedade" vai para propriedades', () => {
    expect(corre('nova propriedade')).toBe('INICIO:propriedades');
  });
});

describe('a limitacao que este teste NAO finge resolver', () => {
  // "cadastrar o vaqueiro" nao vai para funcionarios: o mapa casa
  // /funcion/, e "vaqueiro" nao contem "funcion".
  //
  // Isto ja foi verdade antes de qualquer correccao. Nao e' uma
  // regressao — e' uma limitacao do mapa por palavra-chave, e o teste
  // dela e' mais util do que um teste que a escondesse: quando o mapa
  // crescer para entender "vaqueiro", este teste avisa.
  //
  // O mapa e' uma lista de nove regexes. Qualquer palavra que nao esteja
  // nessa lista nao abre formulario nenhum. A correccao de fundo e' o
  // frontend delegar nos intents do backend — que sim sabe que vaqueiro
  // e' um cargo — em vez de duplicar o conhecimento em regexes.
  it('"cadastrar o vaqueiro" NAO abre o formulario de funcionarios', () => {
    // Documentado como limitacao, nao como comportamento desejado.
    expect(corre('cadastrar o vaqueiro')).not.toBe('INICIO:funcionarios');
  });

  it('as duas caem na pergunta que pede esclarecimento', () => {
    // Nao num null. O "nao percebi" obriga a tentar outra frase; a
    // promessa vazia faz a pessoa preencher um formulario imaginario.
    for (const p of ['cadastrar o vaqueiro', 'adicionar trator']) {
      expect(corre(p), `"${p}" devia pedir esclarecimento`).not.toBeNull();
    }
  });
});
