/**
 * O cadastro da estação meteorológica — do "Nome da estação?" ao `POST`.
 *
 * POR QUE ESTE TESTE EXISTE
 * -----------------------
 * A conversa que o produtor teve chegou até (a), respondeu o nome da estação,
 * e morreu ali. O primeiro defeito (a pergunta sem cadastro aberto) já tem
 * teste em `ia_fonte_clima.test.js`. Este pega no SEGUNDO: o cadastro que se
 * abre e mesmo assim não consegue ser gravado.
 *
 *   `ESQUEMAS_CADASTRO.estacoes` pedia `municipio` — que `EstacaoMeteo` não
 *   tem, logo o servidor deita fora — e marcava `latitude`/`longitude` como
 *   opcionais, quando no modelo são `DecimalField` sem `null`/`blank`. E o
 *   `avancarCadastro` só juntava `propriedade` para funcionários, talhões e
 *   operações: `EstacaoMeteo.propriedade` é `ForeignKey` obrigatória.
 *
 *   O resultado era um produtor que preenchia a conversa inteira e recebia
 *   `Erro ao criar estacoes: {"latitude":["Este campo é obrigatório."]}`.
 *
 * POR QUE UM TESTE QUE LÊ O SERIALIZER
 * ------------------------------------
 * O esquema e o serializer são dois sítios que ninguém lê juntos. Por isso o
 * teste LÊ O SERIALIZER DE VERDADE (`app/api/serializers.py`) e exige que o
 * esquema converse com ele. Comparar o esquema com uma lista escrita aqui
 * passaria com o serializer errado — que é o defeito que este teste apanha.
 *
 * E o segundo bloco corre o `avancarCadastro` real, para ver o PAYLOAD que ia
 * para o `POST`.
 */

import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';

const RAIZ = path.resolve(__dirname, '../..');
const JS = path.join(RAIZ, 'app/static/js/ia-local/ia-local.js');
const SERIALIZERS = path.join(RAIZ, 'app/api/serializers.py');
const MODELOS = path.join(RAIZ, 'app/models/iot.py');
const fonte = fs.readFileSync(JS, 'utf-8');
const py = fs.readFileSync(SERIALIZERS, 'utf-8');
const modelos = fs.readFileSync(MODELOS, 'utf-8');

/** Recorta `const <nome> = …` até ao fecho do valor.
 *
 * O valor pode ser um `{…}` (o dicionário dos esquemas) ou um `[…]` (uma
 * lista de recursos). Assumir sempre `{}` faz o extractor saltar o `[` e
 * contar chavetas até à primeira que encontrar — que é a de uma função
 * qualquer mais abaixo — e devolve um SyntaxError que não aponta para nada.
 */
function extrairConstante(nome) {
  const marco = `const ${nome} =`;
  const inicio = fonte.indexOf(marco);
  if (inicio === -1) throw new Error(`${nome} não existe em ia-local.js`);
  const abre = (() => {
    const ch = fonte.indexOf('{', inicio);
    const colch = fonte.indexOf('[', inicio);
    if (ch === -1) return colch;
    if (colch === -1) return ch;
    return Math.min(ch, colch);
  })();
  const fecha = fonte[abre] === '{' ? '}' : ']';
  let nivel = 0;
  for (let i = abre; i < fonte.length; i += 1) {
    if (fonte[i] === fonte[abre]) nivel += 1;
    else if (fonte[i] === fecha) {
      nivel -= 1;
      if (nivel === 0) return fonte.slice(inicio, i + 1);
    }
  }
  throw new Error(`não consegui fechar ${nome}`);
}

/** Recorta `function <nome>(…) { … }` — com o `async`, se o tiver. */
function extrairFuncao(nome) {
  const marco = `function ${nome}(`;
  let inicio = fonte.indexOf(marco);
  if (inicio === -1) throw new Error(`${nome} não existe em ia-local.js`);
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

/** O bloco Python de uma classe, até à classe seguinte. */
function blocoDaClasse(texto, nomeClasse) {
  const i = texto.indexOf(`class ${nomeClasse}(`);
  if (i === -1) throw new Error(`${nomeClasse} não existe`);
  const prox = texto.indexOf('\nclass ', i + 1);
  return texto.slice(i, prox === -1 ? texto.length : prox);
}

/** Os `fields` que o Python declara no serializer — lidos do Python. */
function camposDoSerializer(nomeClasse) {
  const bloco = blocoDaClasse(py, nomeClasse);
  return (bloco.match(/"([a-z_]+)"/g) || []).map((c) => c.replace(/"/g, ''));
}

/** Os campos do MODELO que NÃO são `null=True` nem `blank=True`.
 *
 * O modelo é a verdade sobre o que o servidor exige: o `serializer` diz o que
 * a API aceita, e o que aceita muda com `read_only_fields`. Quem recusa o
 * `POST` é o `DecimalField` sem `null` — e é no ficheiro do modelo que isso
 * está escrito.
 */
function camposObrigatoriosNoModelo(classeModelo) {
  const defs =
    blocoDaClasse(modelos, classeModelo).match(/^ {4}(\w+)\s*=\s*models\.[\w.]+\((.*?)\)\s*$/gms) ||
    [];
  return defs
    .filter((d) => !/null=True/.test(d) && !/blank=True/.test(d))
    .map((d) => d.match(/^ {4}(\w+)/)[1]);
}

const ESQUEMAS_CADASTRO = new Function(
  `${extrairConstante('ESQUEMAS_CADASTRO')}; return ESQUEMAS_CADASTRO;`
)();

const RECURSOS_COM_PROPRIEDADE = new Function(
  `${extrairConstante('RECURSOS_COM_PROPRIEDADE')}; return RECURSOS_COM_PROPRIEDADE;`
)();

const camposSerializer = camposDoSerializer('EstacaoMeteoSerializer');
const obrigatoriosModelo = camposObrigatoriosNoModelo('EstacaoMeteo');
const esquemaEstacao = ESQUEMAS_CADASTRO.estacoes;
const camposEsquema = esquemaEstacao.map((c) => c.campo);
describe('o esquema da estação fala a língua do serializer', () => {
  it('o serializer ainda existe e tem os campos que o esquema pede', () => {
    // A sanidade do teste: sem isto, "o esquema está errado" passaria à
    // largura no dia em que o serializer mudasse de nome.
    expect(camposSerializer).toContain('nome');
    expect(camposSerializer).toContain('latitude');
    expect(camposSerializer).toContain('longitude');
    expect(camposSerializer).toContain('propriedade');
    expect(obrigatoriosModelo).toContain('latitude');
    expect(obrigatoriosModelo).toContain('longitude');
  });

  it('NÃO pede um campo que o serializer não tem', () => {
    // `municipio` foi o primeiro defeito: o produtor escrevia um município
    // que ninguém guardava. Um campo a mais não dá erro visível — dá um
    // cadastro que perde informação sem nunca dizer que a perde.
    const inventados = camposEsquema.filter((c) => !camposSerializer.includes(c));
    expect(inventados).toEqual([]);
  });

  it('pede, e exige, as coordenadas que o modelo exige', () => {
    // `latitude` e `longitude` eram opcionais no esquema e obrigatórias no
    // modelo. O servidor só descobria isso no fim, depois da conversa inteira.
    for (const campo of ['latitude', 'longitude']) {
      const def = esquemaEstacao.find((c) => c.campo === campo);
      expect(def, `${campo} tem de ser pedido`).toBeTruthy();
      expect(def.obrigatorio, `${campo} tem de ser obrigatório`).toBe(true);
    }
  });
});

describe('o wizard da estação fecha o que o modelo exige', () => {
  it('"estacoes" está na lista dos recursos que recebem propriedade', () => {
    // `EstacaoMeteo.propriedade` é `ForeignKey` obrigatória. Sem o id, o POST
    // é recusado no fim — depois de a pessoa ter preenchido tudo.
    expect(RECURSOS_COM_PROPRIEDADE).toContain('estacoes');
  });

  it('a condição da propriedade não está duplicada em dois sítios', () => {
    // Havia DUAS cópias (finalização por NLP e por campo a campo), e foi essa
    // duplicação que deixou `estacoes` de fora: as duas diziam a mesma coisa
    // e só uma se lembrava do quarto recurso.
    const copias = (fonte.match(/recurso === 'funcionarios' \|/g) || []).length;
    expect(copias, 'a condição voltou a duplicar-se — use RECURSOS_COM_PROPRIEDADE').toBe(0);
  });
});
describe('o payload final da estação', () => {
  /** Corre o `avancarCadastro` real contra o esquema real. */
  function payloadFinal(respostas) {
    const corpo = `
      const ESQUEMAS_CADASTRO = ${JSON.stringify(ESQUEMAS_CADASTRO)};
      const RECURSOS_COM_PROPRIEDADE = ${JSON.stringify(RECURSOS_COM_PROPRIEDADE)};
      let iaCadastroPendente = { recurso: 'estacoes', dados: {}, etapa: 0, esquema: ESQUEMAS_CADASTRO.estacoes };
      const window = { _iaPropPadrao: 7 };
      const getChecklistHTML = () => '';
      const extrairCamposNL = () => null;
      ${extrairFuncao('limparValorNumerico')}
      ${extrairFuncao('avancarCadastro')}
      for (const r of ${JSON.stringify(respostas)}) {
        const out = avancarCadastro(r);
        if (out && typeof out === 'object' && out.finalizar) return out;
        if (iaCadastroPendente === null) return null;
      }
      return null;
    `;

    return new Function(corpo)();
  }

  it('devolve um payload que o serializer aceita', () => {
    // A conversa real: "estaçao met do lucas", a latitude, a longitude.
    const out = payloadFinal(['estaçao met do lucas', '-21.55', '-46.37']);
    expect(out).not.toBeNull();
    expect(out.recurso).toBe('estacoes');
    const d = out.dados;
    expect(d.nome).toBe('estaçao met do lucas');
    expect(d.latitude).toBe('-21.55');
    expect(d.longitude).toBe('-46.37');
    // O dono da estação: a fazenda em foco.
    expect(d.propriedade).toBe(7);
  });

  it('o nome do produtor sobrevive intacto', () => {
    // A frase mais importante da conversa: foi o texto que o produtor
    // escreveu. Apurado ou completado aqui, o cadastro fechava com o nome da
    // estação trocado — e ninguém notava.
    const out = payloadFinal(['  Estação do Lucas  ', '-21.55', '-46.37']);
    expect(out.dados.nome).toBe('Estação do Lucas');
  });

  it('"pular" numa coordenada obrigatória NÃO a grava — pergunta outra vez', () => {
    // O defeito: `obrigatorio: false` deixava "pular" passar, e
    // `limparValorNumerico` devolvia o texto tal e qual. Iria "pular" como
    // latitude para o servidor — que responderia 400, ou pior, um
    // DecimalField a aceitar o que não é número.
    //
    // A conversa que o produtor TEM depois de "pular": o wizard continua
    // aberto à espera do valor. É isso que se verifica — e o valor acaba por
    // chegar, e chega no sítio certo.
    const out = payloadFinal(['Estação Norte', 'pular', '-21.55', '-46.37']);
    expect(out).not.toBeNull();
    expect(out.dados.latitude).toBe('-21.55');
    expect(out.dados.nome).toBe('Estação Norte');
  });

  it('não finaliza enquanto um obrigatório ficou por responder', () => {
    // O outro lado do mesmo defeito: se "pular" fosse aceite, o `POST` saía
    // sem coordenada. O wizard tem de ficar aberto — e é isso que se mede.
    expect(payloadFinal(['Estação Norte', 'pular', '-21.55'])).toBeNull();
    expect(payloadFinal(['Estação Norte', 'pular', '-21.55', 'pular'])).toBeNull();
  });

  it('nenhum payload leva a palavra "pular" como se fosse um dado', () => {
    for (const respostas of [
      ['Estação A', 'pular', '-21.55', '-46.37'],
      ['Estação B', '-21.55', 'pular', '-46.37'],
      ['Estação C', '-21.55', '-46.37', 'pular'],
    ]) {
      const out = payloadFinal(respostas);
      if (!out) continue;
      for (const [k, v] of Object.entries(out.dados)) {
        expect(String(v).toLowerCase(), `${k} = "${v}"`).not.toBe('pular');
      }
    }
  });
});
