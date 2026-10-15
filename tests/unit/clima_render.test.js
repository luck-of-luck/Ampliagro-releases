import { describe, it, expect, beforeAll } from 'vitest';
import fs from 'fs';
import os from 'os';
import path from 'path';

// O que o browser REALMENTE mostraria na página de previsão.
//
// POR QUE ISTE TESTE EXISTE
// --------------------------
// Tudo o que foi feito ao clima foi verificado por HTTP: a view responde
// 200, o JSON traz a coordenada certa, a `fonte` vem no payload. Nada
// disso prova que o browser mostra o número.
//
// E há um caso em que isso falha de verdade: o JS pode construir o
// objeto `previsao` sem `prob_chuva`, e a página mostra as temperaturas
// e omite a chance de chuva — sem nenhum erro, sem HTTP 500, e com
// todos os testes de Python verdes. O render só aparece com o cartão na
// mão.
//
// A humidade é o caso reverso: `umidade: null` está certo no payload, mas
// se a linha do template mostrar "Umidade:" na mesma, quem lê vê um
// número inventado de volta.
//
// O PAYLOAD é o que o endpoint devolveu de verdade, lido do dump. Não é
// um feito à mão: um payload escrito à mão passa a descrever um dia
// diferente do que o utilizador vai ver, e o teste deixa de proteger o
// que protege.

// Caminho ABSOLUTO, e não relativo a `process.cwd()`.
//
// O vitest corre com o cwd no sítio que o launcher definir, não na raiz do
// subir cinco `..` a partir dali dá um caminho que não existe. O erro
// que aparece é "Falta o dump" — que parece o dump não estar gerado,
// quando está. Um erro que aponta para a coisa errada é pior que um
// erro óbvio.
//
// O dump vai para a pasta temporária que o ambiente aprova, e o script
// que o gera lê `CLIMA_RENDER_FIXTURE_DIR` — a MESMA variável. Uma fonte
// de verdade, dois lados.
//
// A variável é o que tirou este caminho do `process.cwd()`: o vitest corre
// com o cwd no sítio que o launcher definir, e subir cinco `..` a partir
// dali dá um caminho que não existe. O erro que aparecia era "Falta o
// dump" — que parece o dump não estar gerado, quando está. Um erro que
// aponta para a coisa errada é pior que um erro óbvio.
//
// E o que tirou o caminho de `C:/Users/lucas/...` do meio do repositório:
// em `ubuntu-latest` esse caminho não existe, o `beforeAll` lançava em vez
// de saltar (decisão certa: um dump em falta DEVE ser barulho), o vitest
// falhava, e o `&&` do job impedia o `npm run test:cjs` de correr. ~380
// checks `.cjs` mortos, e o job vermelho por causa disso.
const SAIDA = process.env.CLIMA_RENDER_FIXTURE_DIR || path.join(os.tmpdir(), 'ampliagro');
const HTML = path.join(SAIDA, 'clima.html');
const JSON_PATH = path.join(SAIDA, 'clima.json');

let html = '';
let payload = null;

beforeAll(() => {
  // Os dumps são feitos por `tests/unit/../../clima_real.py`. Se não
  // existirem, o teste avisa em vez de passar em branco — um teste que
  // pula porque o ficheiro falta parece verde e não verifica nada.
  if (!fs.existsSync(HTML) || !fs.existsSync(JSON_PATH)) {
    throw new Error(
      'Falta o dump da pagina. Corra antes:\n' + '  python tests/gerar_clima_render.py'
    );
  }
  html = fs.readFileSync(HTML, 'utf-8');
  payload = JSON.parse(fs.readFileSync(JSON_PATH, 'utf-8'));
});

/** Extrai uma funcao do template, com o `async` se o tiver. */
function extrai(nome) {
  const re = new RegExp(`(?:async\\s+)?function\\s+${nome}\\s*\\(`);
  const m = re.exec(html);
  if (!m) return null;
  const abre = html.indexOf('{', m.index + m[0].length);
  let nivel = 0;
  for (let k = abre; k < html.length; k += 1) {
    if (html[k] === '{') nivel += 1;
    else if (html[k] === '}') {
      nivel -= 1;
      if (nivel === 0) return html.slice(m.index, k + 1);
    }
  }
  return null;
}

/** Extrai uma declaracao `const|var|let NOME = {...};` inteira. */
function extraiConst(nome) {
  const re = new RegExp(`(?:const|var|let)\\s+${nome}\\s*=\\s*\\{`);
  const m = re.exec(html);
  if (!m) return null;
  const abre = html.indexOf('{', m.index + m[0].length - 1);
  let nivel = 0;
  for (let k = abre; k < html.length; k += 1) {
    if (html[k] === '{') nivel += 1;
    else if (html[k] === '}') {
      nivel -= 1;
      if (nivel === 0) return html.slice(m.index, k + 1) + ';';
    }
  }
  return null;
}

/**
 * Corre `carregarPrevisao` contra o payload real, num DOM de mentira.
 *
 * Devolve o HTML que ela escreveria no container, mais os elementos de
 * cabeçalho — que é onde a origem e o aviso aparecem.
 */
async function renderizar() {
  const doc = globalThis.document;
  // A pagina nao esta no DOM do vitest: cria-se a estrutura minima que a
  // funcao procura por id.
  //
  // A lista e' a que `carregarPrevisao` procura DE FACTO — varrida do dump,
  // nao escrita de memoria. Faltava `captura-badge` (o badge do
  // "Capturado em ..."), e `rotularCaptura(null, ...)` morria em
  // `Cannot read properties of null (reading 'style')`: sete vermelhos que
  // nao eram da pagina, eram do arnes a nao lhe dar o elemento que ela
  // pede. `semSinal` usa os mesmos quatro.
  for (const id of [
    'forecast-cards',
    'alertas-container',
    'source-badge',
    'captura-badge',
    'fonte-coordenadas',
    'aviso-coordenadas',
    'clima-chart',
  ]) {
    let el = doc.getElementById(id);
    if (!el) {
      el = doc.createElement('div');
      el.id = id;
      doc.body.appendChild(el);
    }
  }

  /* O que a funcao fecha por cima, e que tem de vir com ela.
   *
   * MEDIDO: `carregarPrevisao` chamava `rotularFonte(...)` e o arnês só lhe
   * passava `getWeatherIcon`, `renderChart` e `console`. Faltavam três peças
   * que vivem no MESMO `<script>` da página — `FONTES`, `rotularFonte` e
   * `rotularCaptura` — e o resultado era
   * `ReferenceError: rotularFonte is not defined` nos 9 testes deste bloco.
   * Não era defeito da página: era o arnês a correr metade da função.
   *
   * Trazem-se do próprio dump, e não se escrevem à mão: uma cópia escrita aqui
   * seria uma segunda verdade, e é exactamente o que o cabeçalho deste
   * ficheiro diz que este teste não pode ter. Só o `renderChart` fica de fora,
   * porque desenha num canvas que o jsdom não tem — e o que se mede é o DOM
   * que a função escreve, não o gráfico. */
  const prefacio = [extraiConst('FONTES'), extrai('rotularFonte'), extrai('rotularCaptura')]
    .filter(Boolean)
    .join('\n');
  const getWeatherIcon = extrai('getWeatherIcon');
  const carregar = extrai('carregarPrevisao');
  expect(getWeatherIcon, 'getWeatherIcon() nao existe no dump').toBeTruthy();
  expect(carregar, 'carregarPrevisao() nao existe no dump').toBeTruthy();

  const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
  // `carregarPrevisao` chama o `fetch` GLOBAL com o URL do endpoint. E'
  // global de proposito: um `fetch` passado por scope seria sombreado
  // pelo `fetch` que a propria funcao tem dentro.
  globalThis.fetch = () => Promise.resolve({ ok: true, json: () => Promise.resolve(payload) });

  const f = new AsyncFunction(
    'renderChart',
    `${prefacio}\nconst getWeatherIcon = ${getWeatherIcon};\nawait (${carregar})();`
  );
  await f(() => {});

  return {
    cartoes: doc.getElementById('forecast-cards').innerHTML,
    fonte: doc.getElementById('fonte-coordenadas').textContent,
    aviso: doc.getElementById('aviso-coordenadas').textContent,
  };
}

describe('a pagina de previsao renderiza o que o endpoint devolve', () => {
  it('nao cai no catch da pagina', async () => {
    // O catch engole o erro e escreve "Nenhuma previsão disponível".
    // Parece um problema de dados, e e' uma referencia a null no DOM.
    const { cartoes } = await renderizar();
    expect(cartoes).not.toContain('Erro ao carregar');
    expect(cartoes).not.toContain('Nenhuma previsão disponível');
  });

  it('faz um cartao por dia do payload', async () => {
    const { cartoes } = await renderizar();
    const dias = payload.daily.time.length;
    expect(cartoes.split('<div class="stat-card">').length - 1).toBe(dias);
  });

  it('mostra a temperatura maxima do primeiro dia', async () => {
    const { cartoes } = await renderizar();
    const max0 = payload.daily.temperature_2m_max[0];
    expect(cartoes).toContain(`${max0}`);
  });

  it('mostra a chance de chuva, que a API trazia e a pagina escondia', async () => {
    // `prob_chuva` é o dado que existia no payload e nunca aparecia.
    // Se o JS deixar de o montar, os cartões ficam completos e limpos —
    // e a pessoa perde a informação sem nenhum sinal.
    const { cartoes } = await renderizar();
    expect(cartoes).toContain('Chance de chuva');
    const prob0 = payload.daily.precipitation_probability_max[0];
    expect(cartoes).toContain(`${prob0}`);
  });

  it('NAO mostra humidade, porque o payload nao tem', async () => {
    // O `umidade: 50` mostrava 50% em qualquer dia, para qualquer lugar.
    // A linha "Umidade:" com um número inventado é pior do que a
    // ausência: ela treina a pessoa a ignorar o número, e depois o
    // número que importa tambem é ignorado.
    const { cartoes } = await renderizar();
    expect(cartoes).not.toContain('Umidade:');
  });

  it('mostra a origem da localizacao', async () => {
    // Quem lê 27 graus tem de poder ler onde foi medido. Sem isto, um
    // clima de outro estado é indistinguível do clima certo.
    const { fonte } = await renderizar();
    expect(fonte).toContain(payload.fonte_coordenadas);
    expect(fonte.toLowerCase()).toContain('localiza');
  });

  it('nao mostra aviso quando a localizacao e coerente', async () => {
    // Um aviso que aparece quando não há nada a dizer treina a pessoa a
    // ignorá-lo.
    const { aviso } = await renderizar();
    if (!payload.aviso_coordenadas) {
      expect(aviso.trim()).toBe('');
    }
  });

  it('o payload tem coordenada do sitio certo, nao de Brasilia', async () => {
    // A regressão do default. Este teste e' o que impede a volta dele:
    // um dia `payload.latitude` volta a -15.79 e o aviso tem de soar.
    expect(payload.latitude).not.toBeCloseTo(-15.793889, 3);
    expect(payload.fonte_coordenadas).toBeTruthy();
  });
});

describe('o numero que o producer ve bate com o que foi medido', () => {
  it('a temperatura mostrada vem do payload, sem ajuste escondido', async () => {
    // Um "+2 graus de conforto" ou um arredondamento para cima seria
    // uma invenção com bom aspecto. O que sai tem de ser o que entrou.
    const { cartoes } = await renderizar();
    for (const v of payload.daily.temperature_2m_max.slice(0, 3)) {
      expect(cartoes).toContain(`${v}`);
    }
  });

  it('a precipitacao mostrada vem do payload', async () => {
    const { cartoes } = await renderizar();
    const comChuva = payload.daily.precipitation_sum.find((x) => x > 0);
    if (comChuva !== undefined) {
      expect(cartoes).toContain(`${comChuva}mm`);
    }
  });
});
