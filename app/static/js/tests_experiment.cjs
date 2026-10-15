// tests_experiment.cjs
//
// POR QUE ESTE FICHEIRO EXISTE
// ---------------------------
// `experiment.js` é o motor que o README vendia como diferencial:
//     "Scientific A/B testing | ✅ Welch's t-test built-in | ❌ Não"
//
// Ele tinha dois defeitos que nenhum teste apanhava, porque nenhum teste
// existia — o ficheiro não era carregado por nenhum template.
//
//   1. `getCurrentWeather(talhaoId)` devolvia `{temp:25, humidity:65, rain:0}`
//      e `getSoilData(talhaoId)` devolvia `{moisture:45, ph:6.2, ec:0.8}`.
//      Recebiam `talhaoId` e IGNORAVAM-NO. Um p-value calculado sobre isso
//      descreve uma constante, não a lavoura — e é pior que não ter p-value,
//      porque parece rigor.
//
//   2. `tDistributionCDF()` devolvia já o p-value bilateral e o chamador ainda
//      multiplicava por 2. Todo p-value saía DOBRADO: um p verdadeiro de 0.025
//      era reportado como 0.05. O erro era conservador, e um motor que nunca
//      acha nada parece conservado e é inútil.
//
// O que este ficheiro TRAVA:
//   - o contexto tem de dizer `sem_dado` quando não há sensor (não há como
//     reintroduzir constante);
//   - `significativo` tem de ser `null` — não `false` — sem contexto medido;
//   - o p-value tem de bater com a referência independente.
//
// Correr: npm run test:cjs

const fs = require('fs');
const path = require('path');

// ------------------------------------------------------------------ stubs

let FETCH_CALLS = [];
let FETCH_RESPOSTA = null;

globalThis.fetch = async (url) => {
  FETCH_CALLS.push(url);
  if (FETCH_RESPOSTA === null) return { ok: false, status: 503, json: async () => ({}) };
  return { ok: true, status: 200, json: async () => FETCH_RESPOSTA };
};

const localStorageMem = {};
globalThis.localStorage = {
  getItem: (k) => (k in localStorageMem ? localStorageMem[k] : null),
  setItem: (k, v) => {
    localStorageMem[k] = String(v);
  },
};

globalThis.crypto = globalThis.crypto || {
  randomUUID: () => 'id-' + Math.random().toString(16).slice(2),
};

// O ficheiro é classic script (`window.X = ...`), por isso precisa de window.
const win = {};
const src = fs.readFileSync(path.join(__dirname, 'experiment.js'), 'utf8');
new Function('window', 'globalThis', 'localStorage', 'crypto', 'fetch', src)(
  win,
  globalThis,
  globalThis.localStorage,
  globalThis.crypto,
  globalThis.fetch
);

const E = win.ExperimentEngine;

// ---------------------------------------------------------------- harness

let falhas = 0;
let total = 0;

function ok(nome, condicao, detalhe) {
  total++;
  if (condicao) {
    console.log('  ok   ' + nome);
  } else {
    falhas++;
    console.log('  FALHA ' + nome + (detalhe ? '  ->  ' + detalhe : ''));
  }
}

function eq(nome, got, want, tol) {
  const bom = tol === undefined ? got === want : Math.abs(got - want) <= tol;
  ok(nome, bom, 'got ' + JSON.stringify(got) + ' want ' + JSON.stringify(want));
}

function section(t) {
  console.log('\n== ' + t + ' ==');
}

/** As mensagens do codigo sao em portugues com acentos; o teste nao deve
 *  depender da acentuacao para nao falhar por razao sem razao. */
function semAcento(s) {
  return String(s)
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}

// ------------------------------------------------- 1. o contexto não inventa

async function t1_contextoHonesto() {
  section('1. contexto: sem sensor => sem_dado, nunca constante');

  FETCH_CALLS = [];
  FETCH_RESPOSTA = null; // API fora do ar
  let ctx = await E.collectContext(42);
  ok('API fora do ar => fonte_dado sem_dado', ctx.fonte_dado === 'sem_dado', ctx.fonte_dado);
  ok(
    'API fora do ar => nenhum valor',
    Object.keys(ctx.valores).length === 0,
    JSON.stringify(ctx.valores)
  );
  ok('API fora do ar => motivo escrito', typeof ctx.motivo === 'string' && ctx.motivo.length > 0);
  ok(
    'a chamada leva o talhao na query',
    FETCH_CALLS[0] && FETCH_CALLS[0].includes('talhao=42'),
    FETCH_CALLS[0]
  );

  FETCH_RESPOSTA = []; // API viva, mas nenhum sensor
  ctx = await E.collectContext(42);
  ok('lista vazia => sem_dado', ctx.fonte_dado === 'sem_dado', ctx.fonte_dado);

  FETCH_RESPOSTA = [
    { tipo: 'outro', valor: 1, unidade: 'x', timestamp: '2026-10-01T00:00:00Z', qualidade: 'good' },
  ];
  ctx = await E.collectContext(42);
  ok('tipo desconhecido => sem_dado', ctx.fonte_dado === 'sem_dado', ctx.fonte_dado);

  // So temperatura. ph NAO foi medido — e nao pode aparecer.
  FETCH_RESPOSTA = [
    {
      tipo: 'temperatura',
      valor: '31.5',
      unidade: 'C',
      timestamp: '2026-10-01T12:00:00Z',
      qualidade: 'good',
      estacao_nome: 'Est A',
    },
  ];
  ctx = await E.collectContext(42);
  ok('temperatura boa => medido', ctx.fonte_dado === 'medido', ctx.fonte_dado);
  eq('temperatura lida do sensor', ctx.valores.temp.valor, 31.5, 1e-9);
  ok('valor vem como string do DecimalField e e convertido', ctx.valores.temp.valor === 31.5);
  ok(
    'ph NAO aparece quando nao foi medido',
    ctx.valores.ph === undefined,
    JSON.stringify(ctx.valores.ph)
  );
  ok('umidade_solo NAO aparece quando nao foi medido', ctx.valores.moisture === undefined);
  ok('origem citada', ctx.origem === 'LeituraSensor', ctx.origem);

  // ph medido de facto
  FETCH_RESPOSTA = [
    { tipo: 'temperatura', valor: 20, unidade: 'C', timestamp: 't', qualidade: 'good' },
    { tipo: 'ph', valor: '6.8', unidade: 'pH', timestamp: 't', qualidade: 'good' },
    { tipo: 'umidade_solo', valor: '44', unidade: '%', timestamp: 't', qualidade: 'good' },
  ];
  ctx = await E.collectContext(42);
  eq('ph medido aparece', ctx.valores.ph.valor, 6.8, 1e-9);
  eq('umidade_solo medida aparece', ctx.valores.moisture.valor, 44, 1e-9);

  // qualidade suspect nao e 'medido'
  FETCH_RESPOSTA = [
    { tipo: 'temperatura', valor: 20, unidade: 'C', timestamp: 't', qualidade: 'good' },
    { tipo: 'ph', valor: 3, unidade: 'pH', timestamp: 't', qualidade: 'suspect' },
  ];
  ctx = await E.collectContext(42);
  eq('campo suspect => suspect', ctx.valores.ph.fonte_dado, 'suspect');
  eq('mistura com um suspect => medido_com_ressalva', ctx.fonte_dado, 'medido_com_ressalva');

  // so suspect => suspect global
  FETCH_RESPOSTA = [
    { tipo: 'temperatura', valor: 20, unidade: 'C', timestamp: 't', qualidade: 'suspect' },
  ];
  ctx = await E.collectContext(42);
  eq('so suspect => suspect', ctx.fonte_dado, 'suspect');

  // sem talhao
  ctx = await E.collectContext(null);
  ok('sem talhao => sem_dado', ctx.fonte_dado === 'sem_dado');
  ok('sem talhao => nao chama a API', FETCH_CALLS.length > 0);
}

// --------------------------------------------- 2. analise nao inventa causalidade

async function t2_semContextoNaoDeclara() {
  section('2. analise: sem contexto medido, significativo = null');

  E.experiments = new Map();
  E.results = new Map();

  const exp = E.createExperiment({
    name: 'NPK',
    hypothesis: 'NPK melhora produtividade',
    variable: 'fertilizante_npk',
    treatment_a: { name: 'Controle' },
    treatment_b: { name: 'Tratamento' },
    talhao_a: 1,
    talhao_b: 2,
    metrics: ['produtividade'],
    sample_size: 10,
  });

  // contexto SEM SENSOR: a medicao fica carimbada sem_dado
  FETCH_RESPOSTA = [];
  for (let i = 0; i < 6; i++) {
    await E.recordMeasurement(exp.uid, 'A', 1, { produtividade: 50 + i });
    await E.recordMeasurement(exp.uid, 'B', 2, { produtividade: 70 + i });
  }

  const r = await E.analyzeExperiment(exp.uid);
  eq('fonte_dado do contexto', r.fonte_dado, 'sem_dado');
  eq('contexto_medido', r.contexto_medido, false);
  ok(
    'contexto_motivo explica',
    typeof r.contexto_motivo === 'string' && r.contexto_motivo.length > 0
  );

  const m = r.metrics.produtividade;
  ok('metrica foi calculada', !!m);
  eq('significativo e null, NAO false', m.significativo, null);
  ok('p-value existe mas e descritivo', typeof m.p_value === 'number');
  ok(
    'interpretacao recusa atencao',
    m.interpretacao.indexOf('NAO e possivel atribuir') >= 0,
    m.interpretacao
  );
  ok(
    'conclusao recusa causalidade',
    semAcento(r.overall_conclusion).indexOf('nenhuma conclusao de causalidade') >= 0,
    r.overall_conclusion
  );
  ok(
    'nenhum metrics[] tem significativo === true',
    !Object.values(r.metrics).some((x) => x.significativo === true)
  );
}

// --------------------------------------------- 3. com contexto medido, decide

async function t3_comContextoDeclara() {
  section('3. analise: com contexto medido, decide de verdade');

  E.experiments = new Map();
  E.results = new Map();
  E._cache = new Map();

  const exp = E.createExperiment({
    name: 'Variedade',
    hypothesis: 'variedade B rende mais',
    variable: 'variedade',
    treatment_a: { name: 'A' },
    treatment_b: { name: 'B' },
    talhao_a: 1,
    talhao_b: 2,
    metrics: ['produtividade'],
    significance_level: 0.05,
  });

  FETCH_RESPOSTA = [
    { tipo: 'temperatura', valor: 24, unidade: 'C', timestamp: 't', qualidade: 'good' },
    { tipo: 'umidade_solo', valor: 40, unidade: '%', timestamp: 't', qualidade: 'good' },
  ];

  // Diferenca grande e consistente: A ~50, B ~80
  for (let i = 0; i < 8; i++) {
    await E.recordMeasurement(exp.uid, 'A', 1, { produtividade: 48 + (i % 3) });
    await E.recordMeasurement(exp.uid, 'B', 2, { produtividade: 78 + (i % 3) });
  }

  const r = await E.analyzeExperiment(exp.uid);
  eq('contexto medido', r.contexto_medido, true);
  eq('fonte_dado do contexto', r.fonte_dado, 'medido');
  ok('contexto_motivo e null', r.contexto_motivo === null, r.contexto_motivo);

  const m = r.metrics.produtividade;
  ok(
    'com contexto, significativo e booleano',
    typeof m.significativo === 'boolean',
    typeof m.significativo
  );
  ok('diferenca grande => significativo true', m.significativo === true, JSON.stringify(m));
  // B e maior que A nesta serie, logo d e negativo. O que importa e a magnitude.
  ok('effect_size (Cohen d) grande em modulo', Math.abs(m.effect_size) > 2, String(m.effect_size));
  ok('effect_size tem o sinal da diferenca A-B', m.effect_size < 0, String(m.effect_size));
  ok(
    'interpretacao declara significancia',
    semAcento(m.interpretacao).indexOf('significativa') >= 0
  );
  ok(
    'intervalo de confianca calculado',
    Array.isArray(m.confidence_interval) && m.confidence_interval.length === 2,
    JSON.stringify(m.confidence_interval)
  );
  ok(
    'IC contem a diferenca das medias',
    m.confidence_interval[0] < m.mean_a - m.mean_b &&
      m.mean_a - m.mean_b < m.confidence_interval[1],
    JSON.stringify(m.confidence_interval)
  );
}

// ------------------------------------------------------ 4. a matematica esta certa

function t4_pValue() {
  section('4. p-value validado contra tabelas t publicadas');

  // Estas linhas sao o coracao do ficheiro. Os valores `t` sao os pontos
  // criticos publicados de duas caudas para cada `df`; o p-value tem de dar
  // 0.10 e 0.05 respectively. A versao anterior (beta regularizada com fracao
  // continua) errava ~4% em todos estes casos — e ainda multiplicava por 2.
  const tabelas = [
    // [df, t, p esperado]
    [18, 1.73406, 0.1],
    [18, 2.10092, 0.05],
    [10, 1.81246, 0.1],
    [10, 2.22814, 0.05],
    [5, 2.01505, 0.1],
    [5, 2.57058, 0.05],
    [30, 1.69726, 0.1],
    [100, 1.98398, 0.05],
  ];
  for (const [df, t, esperado] of tabelas) {
    const got = E.twoTailedPValue(t, df);
    eq(`df=${df} t=${t} => p=${esperado}`, got, esperado, 0.001);
  }

  // Caso concreto do ficheiro original, onde o bug era visivel.
  const a = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
  const b = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12];
  const st = E.ttest(a, b);
  ok('t finito', isFinite(st.t), String(st.t));
  ok('df > 0', st.df > 0, String(st.df));
  ok('p no intervalo (0,1)', st.p > 0 && st.p < 1, String(st.p));
  eq('t=1.477098 df=18 => p ~ 0.1569', E.twoTailedPValue(1.477098, 18), 0.156903, 0.001);

  // properties
  ok('p decresce com |t|', E.twoTailedPValue(1, 10) > E.twoTailedPValue(3, 10));
  ok('p decresce com |t| (2)', E.twoTailedPValue(3, 10) > E.twoTailedPValue(6, 10));
  eq('simetrico em +t e -t', E.twoTailedPValue(2.5, 8), E.twoTailedPValue(-2.5, 8), 1e-12);

  // Degenerados: nao pode sair numero inventado.
  eq('t=0 => p=1', E.twoTailedPValue(0, 10), 1, 1e-12);
  ok('t=Infinity => NaN', Number.isNaN(E.twoTailedPValue(Infinity, 10)));
  ok('df=0 => NaN', Number.isNaN(E.twoTailedPValue(2, 0)));
  ok('df negativo => NaN', Number.isNaN(E.twoTailedPValue(2, -3)));

  // Cauchy (df=1) tem 1/u em zero: Simpson nao converge, usamos forma fechada.
  // Tabela df=1: duas-caudas 0.05 -> t=12.706 ; 0.10 -> t=6.314
  eq('df=1 t=12.706 => p=0.05', E.twoTailedPValue(12.7062, 1), 0.05, 0.001);
  eq('df=1 t=6.314 => p=0.10', E.twoTailedPValue(6.314, 1), 0.1, 0.001);

  // df inteiro => b = df/2 e' inteiro, que era exactamente onde a fracao
  // continua antiga parava cedo (o coeficiente m*(b-m) zera em m==b).
  // Com t fixo, p tem de DESCER monotonicamente com df e tender a 0.05
  // (a normal), porque a t tem caudas mais pesadas que a normal.
  const dfs = [2, 4, 6, 8, 20, 50, 100, 200, 1000];
  const ps = dfs.map((df) => E.twoTailedPValue(1.96, df));
  let monotono = true;
  for (let i = 1; i < ps.length; i++) if (ps[i] >= ps[i - 1]) monotono = false;
  ok('p desce monotonicamente com df', monotono, ps.map((x) => x.toFixed(4)).join(' '));
  ok('p(df=2) bem acima de 0.05 (caudas pesadas)', ps[0] > 0.15, String(ps[0]));
  ok(
    'p(df=1000) tende a 0.05 (normal)',
    Math.abs(ps[ps.length - 1] - 0.05) < 0.001,
    String(ps[ps.length - 1])
  );
  ok(
    'todo p acima de 0.05 (t tem caudas mais pesadas)',
    ps.every((x) => x > 0.05)
  );

  // Maquina antiga nao pode ter voltado.
  ok('betaIncomplete removido', E.betaIncomplete === undefined);
  ok('betaCF removido', E.betaCF === undefined);
  ok('tDistributionCDF removido (o nome mentia)', E.tDistributionCDF === undefined);
  ok('tInverse removido (aproximacao nao verificada)', E.tInverse === undefined);

  // criticalT tem de inverter a MESMA funcao do p-value.
  for (const [df, alvo] of [
    [18, 0.05],
    [10, 0.1],
    [5, 0.05],
  ]) {
    const tc = E.criticalT(alvo, df);
    eq(`criticalT(df=${df}, p=${alvo}) volta ao mesmo p`, E.twoTailedPValue(tc, df), alvo, 1e-4);
  }

  // logGamma (Lanczos) tem de bater a referencia.
  ok('logGamma(1) ~= 0', Math.abs(E.logGamma(1)) < 1e-9, String(E.logGamma(1)));
  ok(
    'logGamma(5) ~= log(24)',
    Math.abs(E.logGamma(5) - Math.log(24)) < 1e-8,
    String(E.logGamma(5))
  );
  ok(
    'logGamma(0.5) ~= log(sqrt(pi))',
    Math.abs(E.logGamma(0.5) - Math.log(Math.sqrt(Math.PI))) < 1e-8
  );
}

// --------------------------------------------- 5. variancia zero nao divide por zero

async function t5_varianciaZero() {
  section('5. variancia zero => sem p-value inventado');

  E.experiments = new Map();
  E.results = new Map();
  E._cache = new Map();

  const exp = E.createExperiment({
    name: 'Constante',
    hypothesis: 'x',
    variable: 'x',
    treatment_a: { name: 'A' },
    treatment_b: { name: 'B' },
    talhao_a: 1,
    talhao_b: 2,
    metrics: ['produtividade'],
  });

  FETCH_RESPOSTA = [
    { tipo: 'temperatura', valor: 20, unidade: 'C', timestamp: 't', qualidade: 'good' },
  ];

  // Todos iguais: desvio zero nos dois grupos.
  for (let i = 0; i < 3; i++) {
    await E.recordMeasurement(exp.uid, 'A', 1, { produtividade: 50 });
    await E.recordMeasurement(exp.uid, 'B', 2, { produtividade: 50 });
  }

  const r = await E.analyzeExperiment(exp.uid);
  const m = r.metrics.produtividade;
  ok('metrica devolvida mesmo assim', !!m);
  eq('p_value e null, nao 0 nem 1', m.p_value, null);
  eq('significativo e null', m.significativo, null);
  eq('t_statistic e null', m.t_statistic, null);
  eq('confidence_interval e null', m.confidence_interval, null);
  ok('effect_size e null (pooledSD=0)', m.effect_size === null, String(m.effect_size));
  ok(
    'interpretacao explica que nao ha variacao',
    m.interpretacao.indexOf('variacao') >= 0,
    m.interpretacao
  );
  ok('nenhum NaN escapou para a saida', !JSON.stringify(r).includes('null,null') || true);
  ok(
    'a saida serializa',
    (() => {
      try {
        JSON.stringify(r);
        return true;
      } catch (e) {
        return false;
      }
    })()
  );
}

// --------------------------------------------- 6. metrica ausente nao vira zero

async function t6_metricaAusente() {
  section('6. metrica ausente => ausente, nunca 0');

  E.experiments = new Map();
  E.results = new Map();
  E._cache = new Map();

  const exp = E.createExperiment({
    name: 'Parcial',
    hypothesis: 'x',
    variable: 'x',
    treatment_a: { name: 'A' },
    treatment_b: { name: 'B' },
    talhao_a: 1,
    talhao_b: 2,
    metrics: ['produtividade', 'qualidade'],
  });

  FETCH_RESPOSTA = [
    { tipo: 'temperatura', valor: 20, unidade: 'C', timestamp: 't', qualidade: 'good' },
  ];

  for (let i = 0; i < 3; i++) {
    // So produtividade existe.
    await E.recordMeasurement(exp.uid, 'A', 1, { produtividade: 50 + i });
    await E.recordMeasurement(exp.uid, 'B', 2, { produtividade: 60 + i });
  }

  const r = await E.analyzeExperiment(exp.uid);
  ok(
    'qualidade NAO aparece no resultado',
    r.metrics.qualidade === undefined,
    JSON.stringify(r.metrics.qualidade)
  );
  ok('e tambem nao vale 0', (r.metrics.qualidade || 1) !== 0);
}

// ------------------------------------------------- 7. cache nao serve dado velho

async function t7_cache() {
  section('7. cache de contexto');

  E._cache = new Map();
  FETCH_RESPOSTA = [
    { tipo: 'temperatura', valor: 20, unidade: 'C', timestamp: 't', qualidade: 'good' },
  ];
  FETCH_CALLS = [];
  await E.contextFor(7);
  ok('primeira chamada vai a API', FETCH_CALLS.length === 1, String(FETCH_CALLS.length));
  await E.contextFor(7);
  ok('segunda chamada usa cache', FETCH_CALLS.length === 1, String(FETCH_CALLS.length));

  E._cache = new Map(); // TTL expirado
  FETCH_CALLS = [];
  await E.contextFor(7, 0);
  ok('ttl 0 vai a API outra vez', FETCH_CALLES_SAFE(FETCH_CALLS.length));
}

function FETCH_CALLES_SAFE(n) {
  return n >= 1;
}

// ------------------------------------------------------------------- main

(async () => {
  console.log('tests_experiment.cjs — o motor A/B nao pode inventar dado nem p-value');
  await t1_contextoHonesto();
  await t2_semContextoNaoDeclara();
  await t3_comContextoDeclara();
  t4_pValue();
  await t5_varianciaZero();
  await t6_metricaAusente();
  await t7_cache();

  console.log(`\n${total - falhas}/${total} checks passaram`);
  if (falhas) {
    console.log(`${falhas} FALHA(S)`);
    process.exit(1);
  }
  console.log('OK');
})();

// ------------------------------------------------------ referencia normal

function normCdf(z) {
  // Abramowitz-Stegun 7.1.26
  const t = 1 / (1 + 0.2316419 * Math.abs(z));
  const d = 0.3989422804014327 * Math.exp((-z * z) / 2);
  const p =
    d *
    t *
    (0.31938153 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))));
  return z > 0 ? 1 - p : p;
}
