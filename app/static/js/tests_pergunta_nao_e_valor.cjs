/* "como voces chamam esse talhao?"
 *
 * ============================================================================
 * O QUE ESTE TESTE PROVA
 * ============================================================================
 * Cinco passos de cadastro guardam o NOME de uma coisa — talhao, piquete,
 * pessoa, tarefa, estagio de ciclo. A pergunta que o sistema faz ao
 * produtor ("como voces chamam esse talhao?") e' uma PERGUNTA. Se essa frase
 * for guardada como valor, o cadastro grava a propria pergunta no campo:
 *
 *     f.nome = "como voces chamam esse talhao?"
 *     POST /api/talhoes/  { nome: "como voces chamam esse talhao?" }
 *
 * E o pior nao e' o talhao. E' a PROPAGACAO: o nome errado vai para safras,
 * aplicacoes, custo por hectare e relatorios. Ninguem ve erro — o registo
 * existe, tem data, e a data esta certa. E' por isso que a guarda tem de
 * estar ANTES do POST, e nao depois de gravar.
 *
 * O QUE ESTE TESTE FAZ, EM DUAS PASSADAS
 * ============================================================================
 * 1. PASSADA DA PERGUNTA. Coloca cada wizard no passo do nome, escreve a
 *    pergunta, e prova duas coisas ao mesmo tempo:
 *      · NENHUM POST sai com a pergunta como valor (o `fetch` falso regista
 *        todo o corpo nao-GET);
 *      · o campo do nome continua VAZIO e o passo NAO avancou.
 *    A segunda e' a que impede o teste de passar a vazio: se a guarda nao
 *    existisse, o nome seria gravado e o passo avancaria.
 *
 * 2. PASSADA DO CONTROLO. Escreve um nome VALIDO e repete. Aqui o POST tem
 *    de SAIR, com o nome verdadeiro. Sem esta passada, um wizard morto
 *    (uma etapa que nunca faz POST por outro motivo) passaria o teste 1
 *    sem provar nada.
 *
 * ============================================================================
 * PORQUE CARREGAR O FICHEIRO INTEIRO
 * ============================================================================
 * Os testes correm `ia-local.js`, o ficheiro que o navegador carrega, com um
 * `fetch` falso. Um teste que copiasse a guarda para o ficheiro de teste
 * passaria com o bug no sitio.
 *
 * A guarda que se procura chama-se `wizEhPergunta(t)` — a mesma que os
 * passos de safra ja usam. Nao ha casamento de palavra-chave escrito a mao
 * aqui: o teste so verifica o EFEITO (nada sai com a pergunta), para nao
 * acoplar o teste a uma implementacao que pode mudar.
 *
 * NAO DEPENDE DE BROWSER NEM DE REDE: `node` puro, sem deps, como os
 * `tests_*.cjs` que ja aqui estao.
 */
'use strict';

const fs = require('fs');
const vm = require('vm');
const path = require('path');

const RAIZ = path.resolve(__dirname, '..', '..', '..');
/* `IA_LOCAL_SRC` existe para provar que o teste NAO passa a vazio: aponta-se
   para uma copia com a guarda removida e a suite tem de FALHAR. Apontar para
   o ficheiro real (o default) e' o caminho normal. */
const SRC = process.env.IA_LOCAL_SRC || path.join(RAIZ, 'app', 'static', 'js', 'ia-local', 'ia-local.js');

/* A frase do enunciado, palavra por palavra. */
const PERGUNTA = 'como voces chamam esse talhao?';

/* As listas EXACTAMENTE como estavam no ecra quando o produtor perguntou.
   "Talhao 1" e "Talhao 10" estao aqui de proposito: sem os dois, o defeito
   do `includes` por pedaco de palavra e' invisivel. */
const TALHOES = [
  { id: 1, nome: 'Pastagem - Braquiaria', area_hectare: 5 },
  { id: 2, nome: 'Reserva Legal', area_hectare: 12 },
  { id: 3, nome: 'Talhao 1 - Catuai Vermelho', area_hectare: 3.5 },
  { id: 4, nome: 'Talhao 10 - Catuaí Amarelo', area_hectare: 4 },
];
const CULTURAS = [
  { id: 1, nome: 'Abobrinha', ciclo_dias: 120, grupo: 'vegetal' },
  { id: 2, nome: 'Café', ciclo_dias: 900, grupo: 'perene' },
];
const FUNCIONARIOS = [
  { id: 1, nome: 'João da Silva', cargo: 'GERENTE' },
  { id: 2, nome: 'João Souza', cargo: 'CAPATAZ' },
];
const PROPRIEDADES = [{ id: 1, nome: 'Fazenda Boa Esperanca' }];

/* ── tudo o que foi escrito para o servidor ────────────────────────────────
   O registo e' GLOBAL e nunca e' limpo a meio: assim a verificacao final
   ("nenhum POST com a pergunta") vale para o ficheiro inteiro, e nao so
   para o passo que se esta a olhar. */
const escritos = [];
const diagnostico = [];

function resposta(dados) {
  return { ok: true, status: 200, text: async () => JSON.stringify(dados) };
}
function casa(alvo, arr) {
  const q = String(alvo || '').toLowerCase();
  return arr.filter((x) => x.nome.toLowerCase().includes(q));
}
function fetchFalso(url, opts) {
  const u = String(url);
  const metodo = String((opts && opts.method) || 'GET').toUpperCase();
  let corpo = null;
  if (opts && opts.body != null) {
    try {
      corpo = JSON.parse(opts.body);
    } catch (e) {
      corpo = opts.body;
    }
  }
  if (metodo !== 'GET') {
    escritos.push({ metodo, url: u, corpo });
    diagnostico.push(metodo + ' ' + u + ' ' + JSON.stringify(corpo));
  }
  const semQuery = u.split('?')[0];
  if (semQuery === '/api/talhoes/') return Promise.resolve(resposta(TALHOES));
  if (semQuery === '/api/culturas/') {
    const q = (u.split('search=')[1] || '').toLowerCase();
    return Promise.resolve(resposta(q ? casa(decodeURIComponent(q), CULTURAS) : CULTURAS));
  }
  if (semQuery === '/api/funcionarios/') return Promise.resolve(resposta(FUNCIONARIOS));
  if (semQuery === '/api/piquetes/') return Promise.resolve(resposta([]));
  if (semQuery === '/api/propriedades/') return Promise.resolve(resposta(PROPRIEDADES));
  return Promise.resolve(resposta({ results: [] }));
}

/* ── um DOM minimo, o suficiente ── */
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
  vm.createContext(ctx);
  /* Os `set*` sao costuras de teste: o `let` do estado e' de topo de script,
     por isso o codigo acrescentado no fim do ficheiro consegue escrever nele.
     Nao se mexe em `ia-local.js` para isto. */
  vm.runInContext(
    src +
      '\n;globalThis.__ia={' +
      'wizEhPergunta,wizEhInstrucao,wizNaoEhValor,wizSim,wizNao,' +
      'wizDispensavel,wizEscolher,wizList,wizTarefaTitulo,' +
      'wizTalhaoStart,wizTalhaoStep,talhao:()=>wizTalhaoF,setTalhao:(v)=>{wizTalhaoF=v;},' +
      'wizAnimalStep,animal:()=>wizAnimal,setAnimal:(v)=>{wizAnimal=v;},' +
      'wizFuncStart,wizFuncStep,func:()=>wizFunc,setFunc:(v)=>{wizFunc=v;},' +
      'wizTarefaStart,wizTarefaStep,tarefa:()=>wizTarefa,setTarefa:(v)=>{wizTarefa=v;},' +
      'wizSafraStart,wizSafraStep,safra:()=>wizSafra,setSafra:(v)=>{wizSafra=v;}' +
      '};',
    ctx,
    { filename: 'ia-local.js' }
  );
  return ctx.__ia;
}

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
    console.log('  FAIL ' + nome + (detalhe ? '  ->  ' + detalhe : ''));
  }
}
function secao(titulo) {
  console.log('\n' + titulo);
}

/* Nenhum POST pode trazer a pergunta dentro do corpo — seja em `nome`, seja
   em `descricao`, seja em `oque`. Procura em TODO o corpo serializado, e
   nao num campo nomeado, porque o defeito e' "a pergunta vira valor" e o
   campo pode ser qualquer um. */
function postsCom(frase) {
  const alvo = frase.toLowerCase();
  return escritos.filter((e) => JSON.stringify(e.corpo || '').toLowerCase().includes(alvo));
}

(async () => {
  const ia = carregarIa();

  /* ─────────────────────────────────────────────────────────────────────
     0. O QUE ESTA SENDO TESTADO
     ───────────────────────────────────────────────────────────────────── */
  secao('O ficheiro reconhece a pergunta como pergunta');
  t('wizEhPergunta ve a frase do enunciado', ia.wizEhPergunta(PERGUNTA) === true);
  t('... e nao ve um nome normal', ia.wizEhPergunta('Baixada') === false);
  t('... e nao ve "Pasto Sul" (so tem palavra de lista)', ia.wizEhPergunta('Pasto Sul') === false);

  /* Cada fluxo: como se chega ao passo do nome, que campo guarda o valor, e
     o caminho completo ate ao POST para o controlo. */
  const FLUXOS = [
    {
      nome: 'talhao:nome',
      url: '/api/talhoes/',
      preparar: () =>
        ia.setTalhao({ step: 'nome', nome: null, area: null, cultura: null, talhaoId: null }),
      estado: ia.talhao,
      campo: 'nome',
      passo: ia.wizTalhaoStep,
      valor: 'Baixada',
      // O que falta para o POST sair, DEPOIS do nome. Usado na passada da
      // pergunta para obrigar o wizard a completar o cadastro quando a
      // guarda falha — sem isto o POST buggy nunca chegaria a ser escrito
      // e a verificacao "nenhum POST com a pergunta" passaria a vazio.
      completar: ['50', 'pular'],
      ateAoPost: async () => {
        await ia.wizTalhaoStep('Baixada'); // nome
        await ia.wizTalhaoStep('50'); // area
        await ia.wizTalhaoStep('pular'); // cultura
      },
    },
    {
      nome: 'animal:piq_nome',
      url: '/api/piquetes/',
      preparar: () =>
        ia.setAnimal({ step: 'piq_nome', piqNome: null, piqArea: null, piqCap: null }),
      estado: ia.animal,
      campo: 'piqNome',
      passo: ia.wizAnimalStep,
      valor: 'Piquete 1',
      completar: ['5', '1', ''],
      ateAoPost: async () => {
        await ia.wizAnimalStep('Piquete 1'); // nome
        await ia.wizAnimalStep('5'); // area
        await ia.wizAnimalStep('1'); // capacidade
        await ia.wizAnimalStep(''); // talhao: Enter = pular
      },
    },
    {
      nome: 'func:nome',
      url: '/api/funcionarios/',
      preparar: () =>
        ia.setFunc({
          step: 'nome',
          nome: null,
          cargo: null,
          salario: null,
          admissao: null,
          fone: null,
        }),
      estado: ia.func,
      campo: 'nome',
      passo: ia.wizFuncStep,
      valor: 'Joao',
      completar: ['tratorista', '2000', '01/02/2026', ''],
      ateAoPost: async () => {
        await ia.wizFuncStep('Joao'); // nome
        await ia.wizFuncStep('tratorista'); // cargo
        await ia.wizFuncStep('2000'); // salario
        await ia.wizFuncStep('01/02/2026'); // admissao
        await ia.wizFuncStep(''); // telefone: Enter = pular
      },
    },
    {
      nome: 'tarefa:oque',
      url: '/api/atividades/',
      preparar: () =>
        ia.setTarefa({ step: 'oque', oque: null, quando: null, resp: null }),
      estado: ia.tarefa,
      campo: 'oque',
      passo: ia.wizTarefaStep,
      valor: 'adubar o talhao Sul',
      completar: ['amanha', ''],
      ateAoPost: async () => {
        await ia.wizTarefaStep('adubar o talhao Sul'); // oque
        await ia.wizTarefaStep('amanha'); // quando
        await ia.wizTarefaStep(''); // resp: Enter = pular
      },
    },
    {
      nome: 'safra:ciclo_nome',
      url: '/api/estagios-cultura/',
      preparar: () =>
        ia.setSafra({
          step: 'ciclo_nome',
          cultura: CULTURAS[0],
          talhao: TALHOES[2],
          property: null,
          registro: null,
          estagios: 0,
          estagio: null,
        }),
      estado: ia.safra,
      campo: 'estagio',
      passo: ia.wizSafraStep,
      valor: 'floracao',
      completar: [],
      ateAoPost: async () => {
        await ia.wizSafraStep('floracao');
      },
    },
  ];

  /* ─────────────────────────────────────────────────────────────────────
     1. A PASSADA DA PERGUNTA — nada pode sair com a pergunta
     ───────────────────────────────────────────────────────────────────── */
  secao('A pergunta NAO vira valor (nenhum POST com a pergunta)');

  for (const fl of FLUXOS) {
    fl.preparar();
    const passoAntes = fl.estado().step;
    const espelho = await fl.passo(PERGUNTA);
    const e = fl.estado();

    t(
      fl.nome + ': o passo nao avancou com a pergunta',
      e.step === passoAntes,
      'step ' + passoAntes + ' -> ' + e.step
    );
    t(
      fl.nome + ': o campo do nome continua vazio',
      e[fl.campo] == null || e[fl.campo] === '',
      fl.campo + ' = ' + JSON.stringify(e[fl.campo])
    );
    t(
      fl.nome + ': a resposta volta a pedir o nome',
      /nome|estágio|estagio|piquete|pessoa|tarefa|fizer|feito/i.test(String(espelho)),
      String(espelho).slice(0, 100)
    );

    /* Se a guarda falhou, o passo avancou e o cadastro vai arrancar. Leva-se
       o resto do formulario com valores validos ate ao POST para que a
       escrita CORRISTA mesmo acontecer: e' assim que a verificacao "nenhum
       POST com a pergunta" abaixo passa a ter dentes. */
    if (e.step !== passoAntes) {
      for (const x of fl.completar) {
        try {
          await fl.passo(x);
        } catch (err) {
          /* um passo que rebenta a seguir ao defeito tambem e' defeito */
        }
      }
    }
  }

  const comPergunta = postsCom(PERGUNTA);
  t(
    'NENHUM POST saiu com a pergunta como valor',
    comPergunta.length === 0,
    comPergunta.length
      ? JSON.stringify(comPergunta).slice(0, 300)
      : escritos.length + ' escritas, nenhuma com a pergunta'
  );

  /* ─────────────────────────────────────────────────────────────────────
     1b. A MESMA COISA, COM A PALAVRA ERRADA — a imperativaçao
     ─────────────────────────────────────────────────────────────────────

     A guarda acima só fecha a PORTA DAS PERGUNTAS. Conduzida ao vivo, a
     caixa gravava o imperativo como nome:

         "cadastrar uma safra" -> "cultura abobrinha" -> "Escolhe uma"
         => nome = "Escolhe uma",  step = talhao

     E "Escolhe uma" não é frase que o utilizador invente: é o que o sistema
     lhe diz noutros sítios ("escolhe os dois e confirma"). O utilizador
     devolve a instrução ao pé do ouvido e ela vira dado — a classe exacta
     do defeito do `docs/sistema/10.md`, com outra palavra.

     Por isso os passos que gravam texto livre usam `wizNaoEhValor`, e não
     `wizEhPergunta`: a pergunta E a imperativação, as duas.

     A lista é curta de propósito. Cada palavra dentro dela é uma palavra
     que deixa de poder ser um NOME — e é por isso que "Manda", "Deixa" e
     "Escola" ficaram de fora, sendo nomes plausíveis. A cobertura das
     formas verbais está em `tests/sondas/sonda_verbo_imperativo.cjs`.
  */
  secao('A imperativaçao NAO vira valor');

  const IMPERATIVOS = [
    'Escolhe uma',
    'Escolha uma',
    'Sugere um nome',
    'Prefiro outro',
    'Inventa um nome',
    'Surpreende-me',
  ];

  for (const imp of IMPERATIVOS) {
    t('"' + imp + '" é reconhecida como imperativaçao', ia.wizEhInstrucao(imp) === true);
    t(
      '"' + imp + '" não serve como valor',
      ia.wizNaoEhValor(imp) === true
    );

    for (const fl of FLUXOS) {
      fl.preparar();
      const passoAntes = fl.estado().step;
      const espelho = await fl.passo(imp);
      const e = fl.estado();

      t(
        fl.nome + ': "' + imp + '" nao avancou o passo',
        e.step === passoAntes,
        'step ' + passoAntes + ' -> ' + e.step + ' | ' + String(espelho).slice(0, 70)
      );
      t(
        fl.nome + ': "' + imp + '" nao preencheu ' + fl.campo,
        e[fl.campo] == null || e[fl.campo] === '',
        fl.campo + ' = ' + JSON.stringify(e[fl.campo])
      );

      /* Mesma razao da passada 1: se a guarda falhou, o cadastro arranca e
         o POST sai. Leva-se o resto do formulario para que a verificacao
         "nenhum POST com a imperativaçao" tenha dentes, em vez de passar a
         vazio porque nada chegou a ser escrito. */
      if (e.step !== passoAntes) {
        for (const x of fl.completar) {
          try {
            await fl.passo(x);
          } catch (err) {
            /* um passo que rebenta a seguir ao defeito tambem e' defeito */
          }
        }
      }
    }

    const comImp = postsCom(imp);
    t(
      'NENHUM POST saiu com a imperativaçao "' + imp + '"',
      comImp.length === 0,
      comImp.length ? JSON.stringify(comImp).slice(0, 300) : 'nenhuma'
    );
  }

  /* ─────────────────────────────────────────────────────────────────────
     1c. O CONTROLO — um nome que começa como verbo tem de ser aceite
     ─────────────────────────────────────────────────────────────────────

     Sem esta passada, a guarda acima passa a vazio se recusar TUDO.

     O sinal de aceitação é O PASSO AVANÇOU — e não "o campo ficou igual ao
     texto". MEDIDO: `safra:ciclo_nome` grava o nome num POST e guarda o
     registo CRIADO (`w.estagio = created`), portanto
     `estagio === 'Escola'` é falso mesmo quando o nome foi aceite. Um
     teste que verificasse o campo estaria a medir a forma do objecto.

     A EXCEPÇÃO é `wizSim`, e é documentada em vez de escondida:
     "manda" está na lista de "sim" (linha 3077) ao lado de "dale" e "show".
     MEDIDO: `wizNaoEhValor("Manda")` é FALSE — a guarda nova conhece-se
     inocente. Não se arruma aqui porque "manda" em português de chat é
     "manda lá" = sim, e tirá-lo da lista parte a confirmação.
  */
  secao('Um nome que começa como verbo continua a ser nome');

  for (const nome of ['Escolhido', 'Sugerido', 'Preferido', 'Escola', 'Escola Municipal']) {
    for (const fl of FLUXOS) {
      fl.preparar();
      const passoAntes = fl.estado().step;
      await fl.passo(nome);
      t(
        fl.nome + ': "' + nome + '" avancou (aceite como nome)',
        fl.estado().step !== passoAntes,
        'step ' + passoAntes + ' -> ' + fl.estado().step
      );
    }
  }

  secao('Colisao conhecida: wizSim leva "manda" antes do passo de texto');
  t(
    'wizNaoEhValor("Manda") e' + ' FALSO — a guarda nova nao e' + ' a causa',
    ia.wizNaoEhValor('Manda') === false,
    String(ia.wizNaoEhValor('Manda'))
  );
  t(
    'wizSim("Manda") e' + ' VERDADE — e' + ' a lista de "sim" que leva a melhor',
    ia.wizSim('Manda') === true,
    String(ia.wizSim('Manda'))
  );
  t(
    'wizTarefaTitulo("Manda") devolve o texto intacto',
    ia.wizTarefaTitulo('Manda') === 'Manda',
    JSON.stringify(ia.wizTarefaTitulo('Manda'))
  );
  ia.setTarefa({ step: 'oque', oque: null });
  await ia.wizTarefaStep('Manda');
  t(
    'tarefa:oque recusa "Manda" — consequencia da colisao com wizSim',
    ia.tarefa().oque == null,
    'oque = ' + JSON.stringify(ia.tarefa().oque)
  );

  /* ─────────────────────────────────────────────────────────────────────
     2. O CONTROLO — o nome VALIDO tem de chegar ao POST
     ─────────────────────────────────────────────────────────────────────
     Sem esta passada, um wizard que nunca faz POST por outro motivo
     passaria a 1 sem provar nada. Aqui entra-se com um nome verdadeiro e
     exige-se que ele apareca no corpo do POST. */
  secao('O CONTROLO: um nome VALIDO chega ao POST (o gravador funciona)');
  let sawPost = false;
  for (const fl of FLUXOS) {
    fl.preparar();
    await fl.ateAoPost();
    const meus = escritos.filter((e) => e.url.split('?')[0] === fl.url);
    if (!meus.length) {
      console.log(
        '  --   ' + fl.nome + ': esta rota nao chega a POST neste teste (o gravador e' +
          ' verificado nos outros)'
      );
      continue;
    }
    sawPost = true;
    const levaNome = meus.some((e) =>
      JSON.stringify(e.corpo || '').toLowerCase().includes(String(fl.valor).toLowerCase())
    );
    t(
      fl.nome + ': o POST saiu com o nome verdadeiro',
      levaNome,
      JSON.stringify(meus[meus.length - 1].corpo).slice(0, 200)
    );
  }
  t(
    'o gravador de POST viu pelo menos um POST real',
    sawPost,
    diagnostico.join(' | ').slice(0, 300)
  );

  /* ─────────────────────────────────────────────────────────────────────
     3. A VERIFICACAO FINAL, sobre TUDO o que foi escrito
     ───────────────────────────────────────────────────────────────────── */
  secao('Revisao final de todo o trafego gerado');
  const finais = postsCom(PERGUNTA);
  t(
    'nenhum POST do ficheiro inteiro contem a pergunta',
    finais.length === 0,
    finais.length ? JSON.stringify(finais).slice(0, 300) : escritos.length + ' escritas no total'
  );
  t(
    'nenhum valor gravado e igual a pergunta',
    escritos.every((e) =>
      Object.values(e.corpo || {}).every((v) => String(v).toLowerCase() !== PERGUNTA)
    ),
    JSON.stringify(escritos).slice(0, 300)
  );

  console.log('\n' + '-'.repeat(60));
  if (falhas) {
    console.log('\n' + falhas + ' FALHA(S):');
    falhados.forEach((f) => console.log('  - ' + f));
    console.log('\n' + ok + ' ok, ' + falhas + ' falhas');
    process.exit(1);
  }
  console.log(ok + ' ok, 0 falhas');
})().catch((e) => {
  console.log('\nERRO NA SUITE: ' + (e && e.stack ? e.stack : e));
  process.exit(1);
});