/* "qual talhão temos disponível para plantar"
 *
 * ============================================================================
 * O QUE ESTES TESTES PROVAM
 * ============================================================================
 * 1. UMA PERGUNTA NÃO É UMA RESPOSTA. O produtor perguntou quais
 *    talhões estavam livres; o cadastro respondeu "Não achei talhão
 *    \"qual talhão temos disponível para plantar\". Opções: …". A
 *    resposta devolvia a pergunta ao pé do ouvido e repetia a lista
 *    que já estava no ecrã.
 * 2. UMA PERGUNTA NÃO É UM NOME. O casamento antigo era
 *    `nome.includes(frase)` — e a pergunta "qual pastagem temos"
 *    casa o talhão "Pastagem - Braquiaria". Uma safra ficava gravada
 *    no talhão errado sem ninguém ter perguntado nada.
 * 3. `includes` CASA POR PEDAÇO DE PALAVRA. `texto.includes("1")`
 *    casava "Talhao 1", "Talhao 10" e "Safra 2026" ao mesmo tempo.
 *    Aqui o casamento é por palavra inteira.
 * 4. "NÃO TENHO" É RESPOSTA, E CONTINUA A SER. "não tenho talhão"
 *    contém "tem", que é palavra de pergunta: se a pergunta for
 *    testada primeiro, o cadastro nunca mais sai do talhão.
 * 5. PERGUNTA NÃO TROCA DE FLUXO. "qual talhão temos para plantar"
 *    contém "plantar", que é verbo de trigger da safra.
 * 6. O QUE NÃO SE QUEBRA. As respostas normais — "Talhao 1",
 *    "catuai vermelho", "não tenho", "sim", "pular" — continuam a
 *    funcionar exactamente como antes.
 *
 * ============================================================================
 * PORQUÊ CARREGAR O FICHEIRO INTEIRO
 * ============================================================================
 * Estes testes NÃO correm uma reescrita da lógica: correm
 * `ia-local.js`, o ficheiro que o navegador carrega, com um `fetch`
 * falso que serve as listas. Um teste que copiasse o `includes` para o
 * ficheiro de teste passaria com o bug no sitio — que é o que a
 * primeira versão deste ficheiro fazia.
 */
'use strict';

const fs = require('fs');
const vm = require('vm');
const path = require('path');

const RAIZ = path.resolve(__dirname, '..', '..', '..');
const SRC = path.join(RAIZ, 'app', 'static', 'js', 'ia-local', 'ia-local.js');

/* As listas EXACTAMENTE como estavam no ecrã quando o produtor
   perguntou. "Talhao 10" e "Talhao 1" estão aqui de propósito: sem os
   dois, o defeito do `includes` por pedaço de palavra é invisível. */
const TALHOES = [
  { id: 1, nome: 'Pastagem - Braquiaria', area_hectare: 5 },
  { id: 2, nome: 'Reserva Legal', area_hectare: 12 },
  { id: 3, nome: 'Talhao 1 - Catuai Vermelho', area_hectare: 3.5 },
  { id: 4, nome: 'Talhao 10 - Catuaí Amarelo', area_hectare: 4 },
  { id: 5, nome: 'Talhao 2 - Bourbon Amarelo', area_hectare: 2 },
];
const CULTURAS = [
  { id: 1, nome: 'Abobrinha', ciclo_dias: 120, grupo: 'vegetal' },
  { id: 2, nome: 'Café', ciclo_dias: 900, grupo: 'perene' },
  { id: 3, nome: 'Milho', ciclo_dias: 140, grupo: 'grao' },
];
const FUNCIONARIOS = [
  { id: 1, nome: 'João da Silva', cargo: 'GERENTE' },
  { id: 2, nome: 'João Souza', cargo: 'CAPATAZ' },
];

/* As duas frases que o produtor escreveu, palavra por palavra. */
const PERGUNTAS_DO_PRODUTOR = [
  'qual talhão temos disponível para plantar',
  'qual talhão a gente tem disponível',
  'voltagem está disponível',
  'quais talhões estão disponíveis?',
];

let ok = 0;
let falhas = 0;
const falhados = [];
function t(nome, cond, detalhe) {
  if (cond) {
    ok++;
    console.log('  ok   ' + nome);
  } else {
    falhas++;
    falhados.push(nome);
    console.log('  FAIL ' + nome + (detalhe ? '  →  ' + detalhe : ''));
  }
}
function secao(titulo) {
  console.log('\n' + titulo);
}

/* ── o `fetch` falso ──────────────────────────────────────────────────────
   Só o que o cadastro de safra pede. Tudo o resto devolve vazio — e o
   `apiFetch` trata o resto como lista vazia, que é o que acontece em
   produção quando a propriedade não tem nada registado. */
function resposta(dados) {
  return { ok: true, status: 200, text: async () => JSON.stringify(dados) };
}
function casa(alvo, arr) {
  const q = alvo.toLowerCase();
  return arr.filter((x) => x.nome.toLowerCase().includes(q));
}
const chamadas = [];
function fetchFalso(url) {
  chamadas.push(String(url));
  const u = String(url);
  const semQuery = u.split('?')[0];
  if (semQuery === '/api/talhoes/') return Promise.resolve(resposta(TALHOES));
  if (semQuery === '/api/culturas/') {
    const q = (u.split('search=')[1] || '').toLowerCase();
    return Promise.resolve(resposta(q ? casa(decodeURIComponent(q), CULTURAS) : CULTURAS));
  }
  if (semQuery === '/api/funcionarios/') return Promise.resolve(resposta(FUNCIONARIOS));
  return Promise.resolve(resposta({ results: [] }));
}

/* ── um DOM mínimo, o suficiente ── */
function el() {
  const n = {
    tagName: 'DIV',
    children: [],
    attrs: {},
    style: {},
    dataset: {},
    value: '',
    textContent: '',
    innerHTML: '',
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    appendChild() {},
    setAttribute() {},
    getAttribute: () => null,
    removeAttribute() {},
    addEventListener() {},
    removeEventListener() {},
    querySelector: () => null,
    querySelectorAll: () => [],
    getBoundingClientRect: () => ({ width: 0, height: 0, top: 0, left: 0 }),
    focus() {},
    click() {},
    remove() {},
    closest: () => null,
    insertBefore() {},
    cloneNode: () => el(),
    scrollIntoView() {},
  };
  for (const p of ['firstChild', 'lastChild', 'parentNode', 'parentElement']) {
    Object.defineProperty(n, p, { get: () => null });
  }
  return n;
}

function carregarIa() {
  let src = fs.readFileSync(SRC, 'utf8');
  // O ficheiro é um módulo ES. Tira-se o `export` e corre-se como
  // script: o que está a ser testado é o CÓDIGO, não o empacotamento.
  src = src
    .replace(/^export\s+default\s+[^;]+;?[ \t]*$/gm, '')
    .replace(/^export\s*\{[^}]*\};?[ \t]*$/gm, '')
    .replace(/^export\s+/gm, '');
  const ctx = {
    console,
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    Promise,
    URL,
    URLSearchParams,
    TextEncoder,
    TextDecoder,
    AbortController,
    fetch: fetchFalso,
    FormData: class {},
    localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    navigator: { language: 'pt-BR', clipboard: { writeText: async () => {} } },
    location: { href: '', pathname: '/', search: '', reload() {}, assign() {} },
    history: { pushState() {} },
    matchMedia: () => ({ matches: false, addEventListener() {} }),
    requestAnimationFrame: (f) => setTimeout(f, 0),
    alert() {},
  };
  ctx.window = ctx;
  ctx.self = ctx;
  ctx.globalThis = ctx;
  ctx.document = {
    body: el(),
    head: el(),
    documentElement: el(),
    // `getCsrf()` lê `document.cookie` — e um DOM sem `cookie` faz
    // `apiFetch` rebentar ANTES do `fetch`, que é um caminho que só o
    // teste apanha: todas as listas vinham vazias e a suite media o
    // `fetch` errado, não o cadastro.
    cookie: 'csrftoken=teste',
    getElementById: () => null,
    querySelector: () => null,
    querySelectorAll: () => [],
    createElement: () => el(),
    createTextNode: () => ({}),
    addEventListener() {},
    removeEventListener() {},
    readyState: 'complete',
  };
  ctx.iaLocal = null;
  vm.createContext(ctx);
  vm.runInContext(
    src +
      '\n;globalThis.__ia={wizSafraStart,wizSafraStep,wizSafra:' +
      '()=>wizSafra,wizEscolher,wizAcharNome,wizEhPergunta,wizDispensavel,' +
      'wizResiduo,wizSemAcerto,wizList,wizTrigger,wizVincTrigger,' +
      'wizEhInstrucao,wizNaoEhValor,' +
      'WIZ_PASSOS_LISTA};',
    ctx,
    { filename: 'ia-local.js' }
  );
  return ctx.__ia;
}

const ia = carregarIa();

/* Conduz o cadastro de safra até ao passo pedido, como na transcrição:
   "cadastrar uma safra" → "cultura abobrinha" → o nome. */
async function ate(step) {
  await ia.wizSafraStart('vamos cadastrar uma safra');
  await ia.wizSafraStep('cultura abobrinha');
  if (step === 'nome') return ia.wizSafra();
  await ia.wizSafraStep('Safra Abobrinha 2026');
  return ia.wizSafra();
}
async function ateOTalhao() {
  return ate('talhao');
}
async function ateONome() {
  return ate('nome');
}

(async function corre() {
  /* ─────────────────────────────────────────────────────────────────────
     1. A PERGUNTA QUE O PRODUTOR FEZ
     ───────────────────────────────────────────────────────────────────── */
  secao('A pergunta que o produtor fez (a da transcrição)');

  for (const frase of PERGUNTAS_DO_PRODUTOR) {
    const w = await ateOTalhao();
    t(`"${frase}" não apanha o talhão`, w.step === 'talhao' && !w.talhao, `step=${w.step}`);

    const r = await ia.wizSafraStep(frase);

    t(`"${frase}" não volta a escrever a pergunta`, !r.includes(frase));
    // A pergunta completa ou quasi: o eco era a frase inteira dentro de
    // aspas. Sem este `?` o teste passa se a frase aparecer cortada.
    t(
      `"${frase}" não devolve a pergunta entre aspas`,
      !new RegExp('"[^"]*' + frase.split(' ')[0] + '[^"]*"', 'i').test(r),
      r
    );
    t(`"${frase}" devolve a lista de talhões`, /Pastagem - Braquiaria/.test(r), r);
    t(`"${frase}" diz o que fazer a seguir`, /pular/i.test(r), r);
    t(`"${frase}" fica à espera do talhão`, ia.wizSafra().step === 'talhao', ia.wizSafra().step);
  }

  /* ─────────────────────────────────────────────────────────────────────
     2. A PERGUNTA NÃO VIRA TALHÃO
     ───────────────────────────────────────────────────────────────────── */
  secao('A pergunta não escolhe um talhão');

  t(
    '"qual pastagem temos" NÃO casa "Pastagem - Braquiaria"',
    ia.wizEscolher(TALHOES, 'qual pastagem temos').tal === null,
    JSON.stringify(ia.wizAcharNome(TALHOES, 'qual pastagem temos').map((r) => r.item.nome))
  );
  t(
    '"quais talhoes temos" NÃO casa nenhum',
    ia.wizEscolher(TALHOES, 'quais talhoes temos').tal === null
  );
  t(
    '"voltagem esta disponivel" NÃO casa nenhum',
    ia.wizEscolher(TALHOES, 'voltagem esta disponivel').tal === null
  );
  t(
    '"qual talhao esta disponivel para plantar" NÃO casa nenhum',
    ia.wizEscolher(TALHOES, 'qual talhao esta disponivel para plantar').tal === null
  );

  /* ─────────────────────────────────────────────────────────────────────
     3. `includes` POR PEDAÇO DE PALAVRA
     ───────────────────────────────────────────────────────────────────── */
  secao('O casamento é por palavra, não por pedaço de palavra');

  const um = ia.wizEscolher(TALHOES, '1');
  t('"1" vai para Talhao 1, não para Talhao 10', um.tal && um.tal.id === 3, um.tal && um.tal.nome);

  const nomeTodo = ia.wizEscolher(TALHOES, 'Talhao 1 - Catuai Vermelho');
  t('o nome exacto casa', nomeTodo.tal && nomeTodo.tal.id === 3, nomeTodo.tal && nomeTodo.tal.nome);

  const soCatuai = ia.wizEscolher(TALHOES, 'catuai vermelho');
  t(
    '"catuai vermelho" acha o Talhao 1',
    soCatuai.tal && soCatuai.tal.id === 3,
    soCatuai.tal && soCatuai.tal.nome
  );

  const soBourbon = ia.wizEscolher(TALHOES, 'bourbon');
  t(
    '"bourbon" acha o Talhao 2',
    soBourbon.tal && soBourbon.tal.id === 5,
    soBourbon.tal && soBourbon.tal.nome
  );

  const reserva = ia.wizEscolher(TALHOES, 'reserva legal');
  t('"reserva legal" acha a Reserva Legal', reserva.tal && reserva.tal.id === 2);

  const talhaoDoAno = ia.wizEscolher(TALHOES, 'Talhao');
  t(
    'a palavra que não identifica nada NÃO escolhe por sorte',
    talhaoDoAno.tal === null || talhaoDoAno.alternativa.length > 1,
    talhaoDoAno.tal && talhaoDoAno.tal.nome
  );

  const perguntaCultura = ia.wizEscolher(CULTURAS, 'qual cultura temos disponivel');
  t('a pergunta não escolhe cultura', perguntaCultura.tal === null);

  /* ─────────────────────────────────────────────────────────────────────
     4. "NÃO TENHO" É RESPOSTA
     ───────────────────────────────────────────────────────────────────── */
  secao('"Não tenho" continua a ser resposta');

  for (const frase of [
    'não tenho',
    'nao tenho talhao',
    'nenhum',
    'qualquer um',
    'pular',
    'sem talhao',
  ]) {
    t(`"${frase}" é resposta, não pergunta`, ia.wizDispensavel(frase), 'wizDispensavel');
  }

  const w = await ateOTalhao();
  const sem = await ia.wizSafraStep('não tenho');
  t('"não tenho" avança para o ano', ia.wizSafra().step === 'ano', ia.wizSafra().step);
  t('"não tenho" diz que fica sem talhão', /Sem talh/i.test(sem), sem);
  void w;

  const w2 = await ateOTalhao();
  void w2;
  const pular = await ia.wizSafraStep('pular');
  t('"pular" avança para o ano', ia.wizSafra().step === 'ano', ia.wizSafra().step);
  t('"pular" não diz que não achei', !/Não achei/.test(pular), pular);

  /* ─────────────────────────────────────────────────────────────────────
     5. O NOME DA SAFRA NÃO É UMA PERGUNTA
     ───────────────────────────────────────────────────────────────────── */
  secao('O nome da safra não é uma pergunta');

  const w3 = await ateONome();
  const perguntaNome = await ia.wizSafraStep('como vocês chamam isso?');
  t(
    'a pergunta pelo nome não fica gravada como nome',
    ia.wizSafra().nome !== 'como vocês chamam isso?',
    String(ia.wizSafra().nome)
  );
  t('a pergunta pelo nome recebe uma sugestão', /Safra Abobrinha/.test(perguntaNome), perguntaNome);
  t('o fluxo continua à espera do nome', ia.wizSafra().step === 'nome', ia.wizSafra().step);
  void w3;

  const w4 = await ateONome();
  const nomeOK = await ia.wizSafraStep('Safra Abobrinha 2026');
  t('um nome normal continua a ser o nome', ia.wizSafra().nome === 'Safra Abobrinha 2026', nomeOK);
  t('e o fluxo avança para o talhão', ia.wizSafra().step === 'talhao', ia.wizSafra().step);
  void w4;

  /* ─────────────────────────────────────────────────────────────────────
     6. O PREFILL DA FRASE-GATILHO NÃO SE PERDE
     ───────────────────────────────────────────────────────────────────── */
  secao('Quem já disse na frase-gatilho não repete');

  // A excepção mais subtil desta correcção. A guarda de lista devolve
  // a lista quando a frase é uma pergunta — mas a frase-gatilho
  // ("cadastrar uma safra DE ABOBRINHA") ainda não foi lida. Barrar
  // aqui jogava fora o que a pessoa já tinha dito, e obrigava-a a
  // escrever "abobrinha" uma segunda vez.
  await ia.wizSafraStart('vamos cadastrar uma safra de abobrinha');
  const comPrefill = await ia.wizSafraStep('quais culturas vocês têm?');
  t(
    'a cultura da frase-gatilho é usada mesmo com uma pergunta',
    ia.wizSafra().cultura && ia.wizSafra().cultura.nome === 'Abobrinha',
    comPrefill
  );
  t('e o fluxo passa ao nome', ia.wizSafra().step === 'nome', ia.wizSafra().step);

  // A mesma pergunta, agora SEM prefill por usar, tem de mostrar a lista.
  await ia.wizSafraStart('vamos cadastrar uma safra');
  const semPrefill = await ia.wizSafraStep('quais culturas vocês têm?');
  t('sem prefill, a pergunta é respondida com a lista', /Abobrinha/.test(semPrefill), semPrefill);
  t('e o fluxo fica à espera da cultura', ia.wizSafra().step === 'cultura', ia.wizSafra().step);

  /* ─────────────────────────────────────────────────────────────────────
     7. PERGUNTA NÃO TROCA DE FLUXO
     ───────────────────────────────────────────────────────────────────── */
  secao('Uma pergunta não troca de fluxo');

  t(
    'wizTrigger NÃO dispara com "qual talhao temos para plantar"',
    ia.wizTrigger('qual talhao temos para plantar') === false
  );
  t(
    '… mas continua a disparar com "cadastrar nova safra de milho"',
    ia.wizTrigger('cadastrar nova safra de milho') === true
  );
  t(
    '… e com "cadastrar safra na área que tem mais leitura"',
    ia.wizTrigger('cadastrar safra na area que tem mais leitura') === true,
    'a frase tem "tem" mas é comando'
  );

  /* ─────────────────────────────────────────────────────────────────────
     7. O QUE CONTINUA A FUNCIONAR
     ───────────────────────────────────────────────────────────────────── */
  secao('O caminho que já funcionava');

  const w5 = await ateOTalhao();
  const bom = await ia.wizSafraStep('Talhao 2 - Bourbon Amarelo');
  t('um talhão pelo nome exacto passa', ia.wizSafra().talhao && ia.wizSafra().talhao.id === 5, bom);
  t('e o fluxo avança para o ano', ia.wizSafra().step === 'ano', ia.wizSafra().step);
  void w5;

  const w6 = await ateOTalhao();
  const amb = await ia.wizSafraStep('Catuaí');
  t('dois candidatos com a mesma nota → pergunta qual', /Achei 2/.test(amb), amb);
  t('e não escolhe por si', ia.wizSafra().talhao === null);
  t('e continua no talhão', ia.wizSafra().step === 'talhao');
  void w6;

  const w7 = await ateOTalhao();
  const porNumero = await ia.wizSafraStep('Talhao 1');
  t(
    '"Talhao 1" acha o Talhao 1 e não o Talhao 10',
    ia.wizSafra().talhao && ia.wizSafra().talhao.id === 3,
    porNumero
  );
  void w7;

  /* ─────────────────────────────────────────────────────────────────────
     8. O NOME DA SAFRA ERRADO DÁ ERRO, NÃO PERGUNTA
     ───────────────────────────────────────────────────────────────────── */
  secao('Um nome que não existe dá erro limpo');

  const w8 = await ateOTalhao();
  const typo = await ia.wizSafraStep('Talhão Nove');
  t(
    'o erro não repete a pergunta',
    !/Talhão Nove.*Não achei|Não achei talhão "Talhão Nove"/i.test(typo),
    typo
  );
  t('o erro lista os talhões', /Pastagem - Braquiaria/.test(typo), typo);
  t('o eco de um nome curto é útil', /"Talhão Nove"/.test(typo), typo);
  t('o nome errado NÃO avança o fluxo', ia.wizSafra().step === 'talhao', ia.wizSafra().step);
  void w8;

  /* ─────────────────────────────────────────────────────────────────────
     9. O ENTER NÃO CANCELA A PRIMEIRA TAREFA
     ───────────────────────────────────────────────────────────────────── */
  secao('Enter em "qual delas?" não escolhe a primeira');

  // Este é o mesmo defeito de tipo — `nome.includes('')`, que é sempre
  // verdadeiro. Aparecia noutro ficheiro (cancelar tarefa) e aparecia
  // aqui pelo mesmo caminho: um valor que não é um valor a casar com
  // uma lista.
  t(
    'a lista não casa com a string vazia',
    ia.wizAcharNome(TALHOES, '').length === 0,
    JSON.stringify(ia.wizAcharNome(TALHOES, '').length)
  );
  t('… e o wizEscolher devolve "não encontrei"', ia.wizEscolher(TALHOES, '').tal === null);

  /* ─────────────────────────────────────────────────────────────────────
     10. O PASSO ESTÁ DECLARADO, NÃO ADIVINHADO
     ───────────────────────────────────────────────────────────────────── */
  secao('Os passos de lista estão declarados');

  for (const chave of ['safra:cultura', 'safra:talhao', 'vinc:talhao', 'funcrem:alvo']) {
    t(`"${chave}" está em WIZ_PASSOS_LISTA`, !!ia.WIZ_PASSOS_LISTA[chave]);
  }

  /* ─────────────────────────────────────────────────────────────────────
     11. O GUARDA NÃO FECHA A CONVERSA, E NÃO ACEITA UMA INSTRUÇÃO
     ─────────────────────────────────────────────────────────────────────

     ESTA SECÇÃO É O OUTRO LADO DO DEFECTO, E É O QUE FAZ O GUARDA
     SER SEGURO DE USAR.

     Um guarda de "isto é uma pergunta?" só serve se for *selectivo*.
     Um guarda que diz "pergunta" a tudo fecha a conversa: o produtor diz
     o nome da cultura, o sistema insiste que perguntou, e não há caminho
     para a frente sem o produtor decifrar o que o sistema quer.

     11.1  O FALSO POSITIVO
     O `wizEhPergunta` olha para palavras como "qual", "quando", "como",
     "tem", "ha". E há valores legítimos do Ampliagro que contêm essas
     MESMAS palavras:

         "Qualquer"   "Quando"   "Comum"   "Manuel"   "Aluminio"

     Um casamento por sub-cadeia trataria "Qualquer" como pergunta — e
     "Qualquer" é um valor legítimo. O casamento tem de ser por PALAVRA
     INTEIRA, e esta secção prova-o, porque essa prova não se faz sozinha:
     depende da lista de palavras que alguém vai acrescentar daqui a seis
     meses.

     11.2  A INSTRUÇÃO — a metade que faltava
     MEDIDO 2026-10-04, conduzindo a safra a sério:

         "cadastrar uma safra" -> "cultura abobrinha" -> "Escolhe uma"

     gravava `nome: "Escolhe uma"` e avançava. O `wizEhPergunta` não a
     apanha porque "escolhe uma" NÃO é pergunta nenhuma: é uma
     IMPERATIVAÇÃO. E não é frase que o utilizador invente — é o que o
     sistema lhe diz noutros sítios ("escolhe os dois e confirma"). O
     utilizador devolve a instrução ao pé do ouvido e ela vira dado: a
     classe exacta do defeito do `docs/sistema/10.md`, com outra palavra.

     Por isso os passos que gravam texto livre usam `wizNaoEhValor`, e não
     `wizEhPergunta`. Num passo de LISTA a pergunta dá jeito — a lista é a
     resposta — e por isso aí se pergunta primeiro `wizEhPergunta`.
  */
  secao('O guarda não trata uma resposta como pergunta');

  /* O que o produtor diz DEPOIS de uma pergunta. Nenhum destes é pergunta. */
  const RESPOSTAS = [
    // valores de lista
    'Talhao 1', 'Talhao 10', 'Milho', 'Soja', 'Algodao',
    // nomes próprios, com e sem acento
    'Joao Silva', 'Jose da Silva', 'Ana Paula Souza', 'Maria',
    'Ze Carlos', 'Chapeu', 'Balanco', 'Ana e Beto',
    // datas
    '2019', '2026', '12/03/2026', '12-03-2026', '03/2026',
    '15 de marco', 'amanha', 'hoje', 'segunda',
    // metricas
    '10', '10.5', '3 dias', 'duas semanas', 'meio',
    /* Os cinco que interessam: contêm uma palavra de interrogação como
       parte de OUTRA palavra. Um casamento por sub-cadeia falha nisto. */
    'Qualquer', 'Quando', 'Comum', 'Manuel', 'Aluminio',
  ];

  for (const r of RESPOSTAS) {
    t(`"${r}" não é lido como pergunta`, !ia.wizEhPergunta(r));
    /* E também não pode ser lido como INSTRUÇÃO — estas duas palavras
       estão na lista de imperativos e é uma lista curta de propósito. */
    t(`"${r}" não é lido como instrução`, !ia.wizEhInstrucao(r));
  }

  /* E o inverso: uma pergunta verdadeira tem de ser reconhecida, senão o
     guarda é inútil e voltamos ao defeito original. */
  const INTERROGACOES = [
    'Qual talhao?', 'Qual e o talhao?', 'Qual cultura?', 'Como e o nome?',
    'Qual o ano?', 'Quando?', 'Qual delas?', 'Quer qual?',
    'qual o proximo passo', 'qual e a data', 'como se chama',
  ];

  for (const q of INTERROGACOES) {
    t(`"${q}" é reconhecida como pergunta`, ia.wizEhPergunta(q));
    t(`"${q}" não serve como valor`, ia.wizNaoEhValor(q));
  }

  /* As IMPERATIVAÇÕES: não são perguntas, mas também não são valores. */
  const INSTRUCOES = [
    'Escolhe uma', 'Escolha uma', 'Escolhe os dois', 'Sugere um nome',
    'Prefiro outro', 'Inventa um nome', 'Surpreende-me',
  ];

  for (const q of INSTRUCOES) {
    t(`"${q}" não é lido como pergunta`, !ia.wizEhPergunta(q));
    t(`"${q}" é reconhecida como instrução`, ia.wizEhInstrucao(q));
    t(`"${q}" não serve como valor`, ia.wizNaoEhValor(q));
  }

  /* E o mais consequente: nem a pergunta nem a instrução podem virar VALOR.
     Este é o defeito original por outro caminho — `wizEscolher` era o que
     transformava "qual talhao?" no talhão 1. */
  const LISTAS = [TALHOES, CULTURAS, FUNCIONARIOS];
  for (const lista of LISTAS) {
    for (const q of INTERROGACOES.concat(INSTRUCOES)) {
      const escolhido = ia.wizEscolher(lista, q);
      t(
        `"${q}" não escolhe nada de ${lista.length} itens`,
        escolhido === null || escolhido === undefined || escolhido.tal === null
      );
    }
  }

  /* ─────────────────────────────────────────────────────────────────────
     12. O PASSO QUE GRAVA O NOME NÃO ACEITA NENHUM DOS DOIS
     ─────────────────────────────────────────────────────────────────────
     Acima testou-se a função. Aqui testa-se o EFEITO, que é o que interessa:
     o `nome` gravado tem de continuar `null` e o passo tem de continuar
     `nome`. Um guarda que funciona na função e é contornado a três linhas
     mais abaixo não protege nada.
  */
  secao('Uma instrução não vira nome de safra');

  for (const frase of INTERROGACOES.concat(INSTRUCOES)) {
    await ia.wizSafraStart('vamos cadastrar uma safra');
    await ia.wizSafraStep('cultura abobrinha');
    await ia.wizSafraStep(frase);
    const st = ia.wizSafra();
    t(
      `"${frase}" não grava nome nem avança`,
      st.nome === null && st.step === 'nome',
      `nome=${JSON.stringify(st.nome)} step=${st.step}`
    );
  }

  /* ───────────────────────────────────────────────────────────────────── */
  console.log('\n' + '-'.repeat(60));
  if (falhas) {
    console.log(`\n${falhas} FALHA(S):`);
    falhados.forEach((f) => console.log('  - ' + f));
    console.log(`\n${ok} ok, ${falhas} falhas`);
    process.exit(1);
  }
  console.log(`${ok} ok, 0 falhas`);
})().catch((e) => {
  console.log('\nERRO NA SUITE: ' + (e && e.stack ? e.stack : e));
  process.exit(1);
});
