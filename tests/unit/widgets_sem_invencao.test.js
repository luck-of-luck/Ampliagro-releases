import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import vm from 'node:vm';

// "null — null" num cartão de satélite, e "0" num KPI que diz "Sem registros".
//
// O QUE O PRODUTOR VIU NO DASHBOARD
// ----------------------------------
// No canto inferior direito:
//
//     VRA NDVI 10m Sentinel-2        ruvens 0%
//     null — null
//
// E, ao lado:
//
//     MEMÓRIA DA IA
//     0
//     Sem registros
//
// QUATRO INCOERÊNCIAS, E SÃO DUAS CLASSES
// ----------------------------------------
// 1. O backend devolve `ndvi_medio: None`, `sanidade: None`,
//    `cobertura_nuvens: None` — está certo, não há credencial Copernicus.
//    O JS é que traduzia a ausência em texto: `${null} — ${null}` dá
//    "null — null".
//
// 2. `${ndvi.cobertura_nuvens || 0}%` dava "0% de nuvens". Isto é a
//    pior das quatro: é uma afirmação meteorológica. O sistema não
//    consultou satélite nenhum, e afirma que o céu está limpo. Quem
//    decide irrigar por um VRA com "0% de nuvens" decide com base em
//    nada — e o cartão tem o aspeto de uma medição.
//
// 3. O KPI mostrava "0" E "Sem registros". Duas afirmações que se
//    anulam: que se mediu zero, e que não se mediu nada. A segunda é a
//    verdade. E o "0" é o que engana — "0 alertas" convence a pessoa de
//    que está tudo bem; "sem registos" obriga-a a perguntar porque é que
//    o sensor não falou.
//
// É a mesma classe do `umidade: 50` que já foi retirada: um número
// inventado com o aspecto de uma medição.
//
// COMO ESTE TESTE CORRE O CÓDIGO
// -----------------------------
// O ficheiro é avaliado num contexto `vm` próprio, com o `document` de
// que ele precisa.
//
// Três tentativas anteriores cortaram o handler por contagem de chavetes
// e evaluatei-o com `new Function`. Todas falharam com SyntaxError —
// mensagens diferentes por handler ("Unexpected token '.'", "Unexpected
// token 'null'"). Um recorte mal fechado produz código a meio, e o
// parser atira antes de o erro apontar para a causa. Em Node limpo, o
// ficheiro inteiro carrega e devolve 553 caracteres sem "null": o
// problema nunca foi o widget, foi o recorte.
//
// O `vm` também resolve o outro lado: em jsdom, `window` já existe e o
// IIFE do ficheiro escreve nele, onde o `document` é outro. Contexto
// próprio, mock do que o código USA.

const RAIZ = resolve(__dirname, '../..');
const FICHEIRO = resolve(RAIZ, 'app/static/js/top-globais-widgets.js');
// MEDIDO 2026-10-05. Antes isto lia `app/templates/index.html` e nada mais.
// O commit `762bf91` extraiu 772 KB de JavaScript desse template para
// `app/static/js/pagina-index.js`, e as regras que este describe vivem no
// codigo renderizador — que passou a estar no JS.
//
// Ler so o template dava uma leitura que passava por razoes erradas: o
// `not.toContain("buildModernKpiHtml(...)")` continuava verde nao porque a
// regra se cumpre, mas porque a funcao ja nao esta no template. Um `not` que
// passa porque le o ficheiro errado e' uma garantia falsa.
//
// Por isso a regra e' lida dos DOIS ficheiros, e o nome diz isso.
const INDEX = [
  readFileSync(resolve(RAIZ, 'app/templates/index.html'), 'utf8'),
  readFileSync(resolve(RAIZ, 'app/static/js/pagina-index.js'), 'utf8'),
  readFileSync(resolve(RAIZ, 'app/static/js/top-globais-widgets.js'), 'utf8'),
].join('\n');

/** Os payloads que o backend devolve hoje, sem nenhuma fonte ligada. */
const PAYLOADS = {
  'kpi-vra-ndvi': {
    ndvi_medio: null,
    sanidade: null,
    satelite: null,
    cobertura_nuvens: null,
    heatmap_url: null,
    talhao_id: 58,
    motivo: 'Sem credencial Copernicus configurada',
    _loading: false,
  },
  'kpi-weigh-scale': {
    talhao_id: 58,
    sc_ha: null,
    ndvi: null,
    tempo_real: false,
    motivo: 'Nenhuma balança ligada a este talhao',
  },
  'kpi-ai-cultura': {
    lat: -21.37,
    lon: -46.49,
    cultura: null,
    confianca: null,
    fonte: null,
    motivo: 'Sem servico de classificacao',
  },
  'kpi-chuva-1km': {
    lat: -21.37,
    lon: -46.49,
    mm_15min: 0.0,
    mm_1h: 0.0,
    alerta: false,
    _evidencia: '',
  },
  'kpi-praga-ai': {
    praga: null,
    confianca: null,
    acao: null,
    motivo: 'Sem foto submetida',
  },
  'kpi-rota-otimizada': {
    km_total: null,
    tempo_h: null,
    economia_pct: null,
    motivo: 'Sem optimiseizador ligado',
  },
  'kpi-guidance-ab': {
    talhao_id: 58,
    linha: 'A-B Pastagem - Braquiaria',
    precisao_cm: null,
    auto_section: null,
  },
  'kpi-as-applied': {
    gap_pct: null,
    ndvi: null,
    acao: null,
  },
};

function carregarHandlers() {
  const el = () => ({
    style: {},
    classList: { add() {}, remove() {} },
    appendChild() {},
    setAttribute() {},
  });
  const ctx = {
    window: {},
    console,
    fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve({}) }),
    document: {
      getElementById: () => null,
      querySelector: () => null,
      querySelectorAll: () => [],
      createElement: el,
      body: { appendChild() {} },
      addEventListener() {},
    },
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
  };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  vm.runInContext(readFileSync(FICHEIRO, 'utf8'), ctx);

  const tg = ctx.window.TopGlobaisWidgets;
  if (!tg || !tg.handlers) {
    throw new Error('o ficheiro nao expoe window.TopGlobaisWidgets.handlers');
  }
  return tg.handlers;
}

const H = carregarHandlers();

const renderiza = (id, dados) => {
  if (!H[id]) throw new Error(`o handler ${id} nao existe`);
  return H[id](dados);
};

describe('nenhum widget escreve "null" no ecra', () => {
  for (const [id, payload] of Object.entries(PAYLOADS)) {
    it(`${id} nao mostra a palavra "null"`, () => {
      expect(renderiza(id, payload)).not.toContain('null');
    });

    it(`${id} nao mostra "undefined" nem "NaN"`, () => {
      // `NaN` vem de `(null * 100).toFixed(0)`. `undefined` vem de uma
      // chave que o backend não devolve. Ambos parecem um cartão com
      // glitch, e nenhum diz o que fazer.
      const html = renderiza(id, payload);
      expect(html).not.toContain('undefined');
      expect(html).not.toContain('NaN');
    });
  }
});

describe('ausencia de medida nao se transforma em zero', () => {
  it('o NDVI diz "Sem NDVI" e mostra o motivo', () => {
    const html = renderiza('kpi-vra-ndvi', PAYLOADS['kpi-vra-ndvi']);
    expect(html).toContain('Sem NDVI');
    // O motivo diz o que falta. "Sem NDVI" sozinho faz a pessoa
    // procurar o botão; o motivo diz que a chave não está configurada.
    expect(html).toContain('Sem credencial Copernicus');
  });

  it('a cobertura de nuvens NAO aparece como 0%', () => {
    // O teste mais importante deste ficheiro. "0% de nuvens" afirma que
    // o céu está limpo, e não se consultou satélite nenhum.
    const html = renderiza('kpi-vra-ndvi', PAYLOADS['kpi-vra-ndvi']);
    expect(html).not.toMatch(/nuvens\s*0%/);
    expect(html).not.toContain('nuvens');
  });

  it('a chuva hiperlocal diz "Sem leitura", nao "0.0mm"', () => {
    // `mm_15min: 0.0` com `_evidencia: ""`. Mostrar 0.0mm afirma que
    // não chove, e é a forma mais barata de o sistema estar errado.
    const html = renderiza('kpi-chuva-1km', PAYLOADS['kpi-chuva-1km']);
    expect(html).not.toContain('0mm/15min');
    expect(html).toContain('Sem leitura');
  });

  it('a balanca diz "Sem pesagem", nao "null sc/ha"', () => {
    const html = renderiza('kpi-weigh-scale', PAYLOADS['kpi-weigh-scale']);
    expect(html).not.toContain('sc/ha');
    expect(html).toContain('Sem pesagem');
    expect(html).toContain('Nenhuma balança');
  });

  it('a deteccao de cultura diz "Sem deteccao", nao "NaN%"', () => {
    const html = renderiza('kpi-ai-cultura', PAYLOADS['kpi-ai-cultura']);
    expect(html).toContain('Sem detecção');
    expect(html).not.toContain('%');
  });
});

describe('quando ha medida, ela aparece', () => {
  // Um widget que só sabe dizer "sem dado" também está errado: esconde o
  // caso em que o sistema funciona.

  it('o NDVI com valor mostra o valor, o veredicto e o satelite', () => {
    const html = renderiza('kpi-vra-ndvi', {
      ndvi_medio: 0.72,
      sanidade: 'Bom',
      satelite: 'Sentinel-2 L2A',
      cobertura_nuvens: 12,
      heatmap_url: '/api/talhao/58/ndvi-heatmap/',
      talhao_id: 58,
      data_captura: '2026-10-01T10:00:00',
    });
    expect(html).toContain('0.72');
    expect(html).toContain('Bom');
    expect(html).toContain('Sentinel-2');
    expect(html).toContain('nuvens 12%');
    expect(html).toContain('2026-10-01');
  });

  it('a chuva com evidencia mostra os milimetros', () => {
    const html = renderiza('kpi-chuva-1km', {
      mm_15min: 2.4,
      mm_1h: 8.1,
      alerta: true,
      _evidencia: 'radar-link',
    });
    expect(html).toContain('2.4mm/15min');
    expect(html).toContain('8.1mm/1h');
  });

  it('a balanca com leitura mostra sc/ha', () => {
    const html = renderiza('kpi-weigh-scale', { sc_ha: 68.4, ndvi: 0.7, tempo_real: true });
    expect(html).toContain('68.4');
    expect(html).toContain('sc/ha');
    expect(html).toContain('tempo real');
  });

  it('a cultura detectada mostra o nome e a confianca', () => {
    const html = renderiza('kpi-ai-cultura', {
      cultura: 'Soja',
      confianca: 0.92,
      fonte: 'satelite',
    });
    expect(html).toContain('Soja');
    expect(html).toContain('92%');
  });
});

describe('o KPI sem dado nao mostra 0', () => {
  // "MEMORIA DA IA: 0 — Sem registros" na imagem. Cada uma das duas
  // partes é inofensiva sozinha; juntas, dizem que se mediu zero E que
  // não se mediu nada.

  it('o bloco de KPI nao usa "0" como valor de ausencia', () => {
    expect(INDEX).not.toContain("buildModernKpiHtml(wTitle, '0', 'Sem registros'");
  });

  it('usa um travessao e diz "Sem dado"', () => {
    expect(INDEX).toContain("'—'");
    expect(INDEX).toContain('Sem dado');
  });

  it('nenhum sitio constroi "0" ao lado de "Sem registros"', () => {
    expect(INDEX).not.toMatch(/'0'\s*,\s*'Sem registros'/);
  });
});

describe('o widget do NDVI nao inventa uma imagem de satelite', () => {
  it('sem medicao, mostra um aviso em vez de um src vazio', () => {
    // O `onerror="display:none"` antigo escondia a imagem e deixava um
    // buraco no cartão, sem dizer porquê.
    const html = renderiza('kpi-vra-ndvi', PAYLOADS['kpi-vra-ndvi']);
    expect(html).not.toMatch(/<img src="/);
    expect(html).toContain('Sem imagem de satélite');
  });

  it('com medicao, mostra a imagem', () => {
    const html = renderiza('kpi-vra-ndvi', {
      ndvi_medio: 0.6,
      heatmap_url: '/api/talhao/58/ndvi-heatmap/',
      talhao_id: 58,
    });
    expect(html).toMatch(/<img src="\/api\/talhao\/58\/ndvi-heatmap\/"/);
  });
});
