// tests_experimento_sync.cjs
//
// POR QUE ESTE FICHEIRO EXISTE
// -----------------------------
// O `tests_experiment.cjs` prova que o motor nao inventa dado nem p-value. Este
// prova que o que o produtor mediu **chega ao servidor, uma vez**.
//
// O problema concreto que este ficheiro fecha
// --------------------------------------------
// O produtor esta no talhao, sem rede. Mede 40 vezes. A rede volta. A rede
// cai a meio do envio.
//
// O `app/static/js/data-sync.js` faz `item.id ? PUT : POST`. Se o POST chega ao
// servidor mas a resposta nao chega ao cliente, `item.id` continua vazio, o
// produtor volta a sincronizar, e o servidor cria um **duplicado** — sem forma
// de saber que e' o mesmo registo. Duplicar o mesmo fato e' pior do que nao o
// guardar: a analise estatistica passa a contar a mesma medicao duas vezes.
//
// A solucao no cliente e' um `uid` gerado ANTES do envio, e no servidor um
// upsert por `uid`. Este ficheiro prova os dois lados.
//
// O QUE ESTE FICHEIRO NAO PROVA
// -----------------------------
// Que o Django aceita o payload. Isso e' Python, e esta em
// `tests/test_experimento_sync.py`. O JS envia um corpo; o Python responde.

const fs = require('fs');
const path = require('path');

let falhas = 0;
let total = 0;

function ok(nome, condicao, detalhe) {
  total++;
  if (condicao) console.log('  ok   ' + nome);
  else {
    falhas++;
    console.log('  FALHA ' + nome + (detalhe ? '  ->  ' + detalhe : ''));
  }
}

function eq(nome, got, want) {
  ok(nome, got === want, 'got ' + JSON.stringify(got) + ' want ' + JSON.stringify(want));
}

function section(t) {
  console.log('\n== ' + t + ' ==');
}

// ------------------------------------------------------- stub do servidor

// Um servidor de mentira que reproduz a semantica do Django: `uid` unico,
// upsert em vez de inserir.
//
// O comportamento e' DIRIGIDO POR ESTADO, e nao por troca de funcao. A primeira
// versao deste ficheiro reatribuia `servidor.fetch` depois de o motor estar
// carregado — e o motor tinha capturado a referencia antiga. Resultado: os
// testes "viam" um servidor sem sensores e davam 5 falhas que nao eram do
// produto. Trocar `fetch` depois da captura nao muda nada em JS; so mudar o
// estado muda.
function servidorFalso(opts) {
  const o = opts || {};
  const estado = {
    experimentos: new Map(), // uid -> {id, ...}
    medicoes: new Map(), // uid -> {...}
    proximoId: 1,
    pedidos: [],
    online: o.online !== false,
    // "Resposta perdida": o pedido CHEGA ao servidor e e' gravado, mas o cliente
    // nunca recebe a resposta. E' o cenario que produz duplicados, e o unico
    // que `data-sync.js` nao sabe tratar. `true` = perda a proxima resposta.
    perderResposta: o.perderResposta === true,
    // O que o endpoint de sensores devolve. `null` = responde 503 (sem sensor).
    // Trocar isto e' como se troca o comportamento de um sensor real.
    sensores: o.sensores === undefined ? [] : o.sensores,
  };

  const responder = async (url, init) => {
    if (!estado.online) throw new Error('Failed to fetch');
    const init2 = init || {};
    estado.pedidos.push({ url, metodo: init2.method, corpo: init2.body });

    if (url.indexOf('leituras-sensor') >= 0) {
      if (estado.sensores === null) return { ok: false, status: 503, json: async () => ({}) };
      return { ok: true, status: 200, json: async () => estado.sensores };
    }

    if (url.indexOf('/api/experimentos/') === 0 && init2.method === 'POST') {
      const corpo = JSON.parse(init2.body);
      if (estado.experimentos.has(corpo.uid)) {
        return { ok: true, status: 200, json: async () => estado.experimentos.get(corpo.uid) };
      }
      const gravado = Object.assign({}, corpo, { id: estado.proximoId++, total_medicoes: 0 });
      estado.experimentos.set(corpo.uid, gravado);
      return { ok: true, status: 201, json: async () => gravado };
    }

    if (url.indexOf('/api/medicoes-experimentais/lote/') === 0 && init2.method === 'POST') {
      const { medicoes } = JSON.parse(init2.body);
      let criados = 0;
      let ja_existiam = 0;
      let rejeitados = 0;
      const erros = [];
      medicoes.forEach((m, i) => {
        if (estado.medicoes.has(m.uid)) {
          ja_existiam++;
          return;
        }
        if (!m.registado_em) {
          rejeitados++;
          erros.push({ indice: i, erro: { registado_em: ['obrigatorio'] } });
          return;
        }
        estado.medicoes.set(m.uid, Object.assign({}, m, { id: estado.proximoId++ }));
        criados++;
      });
      const resposta = { criados, ja_existiam, rejeitados, erros };
      if (estado.perderResposta) {
        // Grava, e depois falha como se a rede tivesse morrido no caminho de
        // volta. O cliente nao sabe que gravou.
        estado.perderResposta = false;
        throw new Error('Failed to fetch');
      }
      return { ok: true, status: 200, json: async () => resposta };
    }

    if (url.indexOf('/api/experimentos/') === 0) {
      const lista = [...estado.experimentos.values()];
      return { ok: true, status: 200, json: async () => ({ count: lista.length, results: lista }) };
    }

    return { ok: false, status: 404, json: async () => ({}) };
  };

  estado.fetch = responder;
  return estado;
}

// ---------------------------------------------------------- carregar o motor

function carregar(servidor) {
  const localStorageMem = {};
  globalThis.localStorage = {
    getItem: (k) => (k in localStorageMem ? localStorageMem[k] : null),
    setItem: (k, v) => {
      localStorageMem[k] = String(v);
    },
  };
  globalThis.fetch = servidor.fetch;
  globalThis.document = { cookie: 'csrftoken=abc123' };
  // O motor regista um listener de 'online' no arranque. Sem isto, `window`
  // tem de existir e aceitar addEventListener.
  const listeners = {};
  const win = {
    addEventListener: (nome, fn) => {
      listeners[nome] = fn;
    },
    disparar: (nome) => {
      if (listeners[nome]) return listeners[nome]();
    },
  };
  globalThis.getCSRFToken = undefined;
  delete globalThis.getCSRFToken;

  const src = fs.readFileSync(path.join(__dirname, 'experiment.js'), 'utf8');
  new Function('window', 'globalThis', 'localStorage', 'fetch', 'document', 'crypto', src)(
    win,
    globalThis,
    globalThis.localStorage,
    globalThis.fetch,
    globalThis.document,
    globalThis.crypto
  );
  return { E: win.ExperimentEngine, win, storage: localStorageMem };
}

const LEITURA_SENSOR = [
  {
    tipo: 'temperatura',
    valor: 24,
    unidade: 'C',
    timestamp: '2026-10-01T12:00:00Z',
    qualidade: 'good',
  },
  {
    tipo: 'umidade_solo',
    valor: 40,
    unidade: '%',
    timestamp: '2026-10-01T12:00:00Z',
    qualidade: 'good',
  },
];

// ============================================================ 1. o uid

function t1_uid() {
  section('1. uid: gerado no cliente, antes do envio, unico');

  const servidor = servidorFalso();
  const { E } = carregar(servidor);
  E.experiments = new Map();
  E.results = new Map();

  const exp = E.createExperiment({ name: 'NPK', hypothesis: 'melhora' });

  ok('o experimento tem uid', typeof exp.uid === 'string' && exp.uid.length > 0, String(exp.uid));
  eq('nasce por sincronizar (o id do servidor ainda nao existe)', exp._sincronizado, false);
  eq('o id do servidor comeca a null', exp.id, null);

  const uids = new Set();
  for (let i = 0; i < 200; i++) uids.add(E._novoUid());
  eq('200 uids, 200 distintos', uids.size, 200);

  ok('o uid nao e o id (o id ainda nao foi atribuido)', exp.uid !== exp.id);
}

// ==================================== 2. idempotencia: o mesmo push duas vezes

async function t2_idempotencia() {
  section('2. idempotencia: a resposta perde-se, o cliente reenvia, o servidor NAO duplica');

  const servidor = servidorFalso({ sensores: LEITURA_SENSOR, perderResposta: true });
  const { E } = carregar(servidor);
  E.experiments = new Map();
  E.results = new Map();

  const exp = E.createExperiment({ name: 'NPK', hypothesis: 'melhora', talhao_a: 1, talhao_b: 2 });

  for (let i = 0; i < 4; i++) {
    await E.recordMeasurement(exp.uid, 'A', 1, { produtividade: 50 + i });
    await E.recordMeasurement(exp.uid, 'B', 2, { produtividade: 70 + i });
  }
  eq('8 medicoes marcadas pendentes', E._contarPendentes(), 8);

  // --- 1a tentativa: o servidor GRAVA e a resposta perde-se ---
  const r1 = await E.sincronizar();
  ok('1a tentativa: o cliente acha que falhou', r1.ok === false, JSON.stringify(r1));
  eq('1a tentativa: o servidor JA gravou as 8', servidor.medicoes.size, 8);
  eq('1a tentativa: o cliente nao sabe, mantem as 8 pendentes', E._contarPendentes(), 8);
  eq('1a tentativa: o experimento tambem ficou gravado', servidor.experimentos.size, 1);

  // --- 2a tentativa: o cliente reenvia tudo ---
  const r2 = await E.sincronizar();
  ok('2a tentativa: foi a ok', r2.ok, JSON.stringify(r2));
  eq('2a tentativa: o servidor contou-as como ja existiam', r2.ja_existiam, 8);
  eq('2a tentativa: criou ZERO novas', r2.criados, 0);
  eq('o servidor tem 8 medicoes, nao 16', servidor.medicoes.size, 8);
  eq('e nao ha uid duplicado', servidor.medicoes.size, new Set([...servidor.medicoes.keys()]).size);
  eq('nada ficou pendente', E._contarPendentes(), 0);

  // --- 3a tentativa: nao ha nada para mandar ---
  const r3 = await E.sincronizar();
  ok('3a tentativa, sem pendentes, nao faz nada e nao falha', r3.ok, JSON.stringify(r3));
  eq('o servidor continua com 8', servidor.medicoes.size, 8);

  console.log('');
  console.log('  Este e' + String.fromCharCode(39) + 'o teste que o data-sync.js nao passa:');
  console.log('  ele faria 8 POST por tentativa, e o servidor gravaria 16.');
}

// ============================== 3. a rede cai entre criar e sincronizar

async function t3_offlinePrimeiro() {
  section('3. o produtor mede offline, sem nunca ter sincronizado');

  const servidor = servidorFalso({ online: false, sensores: LEITURA_SENSOR });
  const { E } = carregar(servidor);
  E.experiments = new Map();
  E.results = new Map();

  const exp = E.createExperiment({
    name: 'Variedade',
    hypothesis: 'B rende mais',
    talhao_a: 1,
    talhao_b: 2,
  });
  const r0 = await E.sincronizar();
  ok('sincronizar offline nao lanca', r0.ok === false);
  eq('e nao criou nada', servidor.experimentos.size, 0);

  // O produtor continua a trabalhar: e' o caso normal no talhao.
  for (let i = 0; i < 3; i++) {
    await E.recordMeasurement(exp.uid, 'A', 1, { produtividade: 50 + i });
    await E.recordMeasurement(exp.uid, 'B', 2, { produtividade: 60 + i });
  }
  eq('6 medicoes measureadas offline e por enviar', E._contarPendentes(), 6);

  servidor.online = true;
  const r = await E.sincronizar();
  ok('quando a rede volta, sobe', r.ok, JSON.stringify(r));
  eq('1 experimento', servidor.experimentos.size, 1);
  eq('6 medicoes', servidor.medicoes.size, 6);

  // A ORDEM importa: o experimento tem de subir antes das medicoes, senao a
  // medicao fica orfa.
  const primeiroExperimento = servidor.pedidos.findIndex(
    (p) => p.url.indexOf('/api/experimentos/') === 0 && p.metodo === 'POST'
  );
  const primeiraLote = servidor.pedidos.findIndex((p) => p.url.indexOf('/lote/') >= 0);
  ok(
    'o experimento sobe antes das medicoes',
    primeiroExperimento < primeiraLote,
    `${primeiroExperimento} vs ${primeiraLote}`
  );
}

// ==================================== 4. o contexto e a fonte via com a medicao

async function t4_contextoVia() {
  section('4. a evidencia e o carimbo fonte_dado viajam com a medicao');

  const servidor = servidorFalso({ sensores: LEITURA_SENSOR });
  const { E } = carregar(servidor);
  E.experiments = new Map();
  E.results = new Map();
  E._cache = new Map();

  const exp = E.createExperiment({ name: 'X', hypothesis: 'h', talhao_a: 1, talhao_b: 2 });

  await E.recordMeasurement(exp.uid, 'A', 1, { produtividade: 55 });
  await E.sincronizar();

  const guardada = [...servidor.medicoes.values()][0];
  ok('o contexto foi enviado', !!guardada.contexto);
  eq('o carimbo fonte_dado foi enviado', guardada.fonte_dado, 'medido');
  eq('a temperatura guarda-se', guardada.contexto.clima.temp.valor, 24);
  eq('e guarda o seu proprio fonte_dado', guardada.contexto.clima.temp.fonte_dado, 'medido');
  eq(
    'o registado_em e' + String.fromCharCode(39) + ' o relogio do produtor, em ISO',
    typeof guardada.registado_em,
    'string'
  );

  // O servidor nao pode aceitar o relogio do cliente como "quando chegou".
  ok('sincronizado_em nao viaja no payload', !('sincronizado_em' in guardada));
}

// ====================== 5. sem sensor: a medicao sobe com 'sem_dado', nao com 0

async function t5_semSensor() {
  section('5. sem sensor, a medicao sobe na mesma — marcada sem_dado');

  // O sensor nunca responde: e' o que acontece numa propriedade sem estacao.
  const servidor = servidorFalso({ sensores: null });
  const { E } = carregar(servidor);
  E.experiments = new Map();
  E.results = new Map();
  E._cache = new Map();

  const exp = E.createExperiment({ name: 'Y', hypothesis: 'h', talhao_a: 1, talhao_b: 2 });

  await E.recordMeasurement(exp.uid, 'A', 1, { produtividade: 50 });
  const r = await E.sincronizar();

  ok('a medicao subiu mesmo sem sensor', r.criados >= 2, JSON.stringify(r));
  const guardada = [...servidor.medicoes.values()][0];
  eq('marcada sem_dado', guardada.fonte_dado, 'sem_dado');
  eq('e sem contexto inventado', Object.keys(guardada.contexto.clima || {}).length, 0);
}

// ==================================== 6. item rejeitado nao derruba o lote

async function t6_rejeitado() {
  section('6. uma medicao mau nao perde as boas');

  const servidor = servidorFalso({ sensores: LEITURA_SENSOR });
  const { E } = carregar(servidor);
  E.experiments = new Map();
  E.results = new Map();
  E._cache = new Map();

  const exp = E.createExperiment({ name: 'Z', hypothesis: 'h', talhao_a: 1, talhao_b: 2 });

  await E.recordMeasurement(exp.uid, 'A', 1, { produtividade: 50 });
  await E.recordMeasurement(exp.uid, 'B', 2, { produtividade: 60 });
  // Uma terceira, com a data invalida — o servidor falso rejeita.
  const m3 = await E.recordMeasurement(exp.uid, 'A', 1, { produtividade: 70 });
  m3.timestamp = null;

  const r = await E.sincronizar();
  ok('o lote nao foi ao chao', servidor.medicoes.size >= 2, JSON.stringify(r));
  ok('as duas boas subiram', servidor.medicoes.size === 2, String(servidor.medicoes.size));
  ok('e a mau continua pendente para nova tentativa', m3._pendente === true, String(m3._pendente));
}

// ==================================== 7. pull nao deita fora o que e' so local

async function t7_pull() {
  section('7. puxar do servidor e' + String.fromCharCode(39) + ' um merge, nao uma substituicao');

  const servidor = servidorFalso({ sensores: LEITURA_SENSOR });
  const { E } = carregar(servidor);
  E.experiments = new Map();
  E.results = new Map();
  E._cache = new Map();

  // O que o produtor mediu offline e ainda nao subiu.
  const expLocal = E.createExperiment({ name: 'SoLocal', hypothesis: 'h' });
  E.experiments.set(expLocal.uid, expLocal);
  await E.recordMeasurement(expLocal.uid, 'A', 1, { produtividade: 50 });

  // E o que ja esta no servidor, de outro dispositivo.
  servidor.experimentos.set('uid-do-outro-dispositivo', {
    id: 99,
    uid: 'uid-do-outro-dispositivo',
    nome: 'DeOutroTelemovel',
    metricas: [],
    total_medicoes: 4,
  });

  const r = await E.puxarDoServidor();
  ok('pull foi a ok', r.ok, JSON.stringify(r));
  eq('trouxe o experimento novo', r.novos, 1);
  ok('o experimento do outro dispositivo chegou', E.experiments.has('uid-do-outro-dispositivo'));

  // O que era so local tem de continuar la.
  ok('o experimento local NAO foi deitado fora', E.experiments.has(expLocal.uid));
  eq('e as medicoes locais continuam pendentes', E._contarPendentes(), 1);
  eq('o numero de medicoes do local nao encolheu', E.results.get(expLocal.uid).length, 1);
}

// ------------------------------------------------------------------- main

(async () => {
  console.log('tests_experimento_sync.cjs — a medicao do produtor tem de chegar uma vez so');
  t1_uid();
  await t2_idempotencia();
  await t3_offlinePrimeiro();
  await t4_contextoVia();
  await t5_semSensor();
  await t6_rejeitado();
  await t7_pull();

  console.log(`\n${total - falhas}/${total} checks passaram`);
  if (falhas) {
    console.log(`${falhas} FALHA(S)`);
    process.exit(1);
  }
  console.log('OK');
})();
