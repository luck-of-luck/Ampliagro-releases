// =============================================================================
// tests_proativo.cjs — a fila do motor proativo vista pelo navegador.
//
// POR QUE ESTE ARQUIVO TESTA O QUE TESTA
// =======================================
// O núcleo puro do polling — a guarda, o parser do modelo e o ciclo — é o que
// mais quebra e menos se testa. A razão é sempre a mesma: ele só falha em
// condições de concorrência e de.device, e "funciona no meu navegador" não é
// evidência de nada. Por isso `decidirTentativa`, `interpretarAchados` e
// `criarPoller` recebem tudo por parâmetro — sem DOM, sem relógio, sem rede.
//
// A REGRA DE OURO DESTE ARQUIVO:
//
//   O MODELO NUNCA RACIOCINA COM A GPU OCUPADA, NUNCA COM A ABA ESCONDIDA, E
//   NUNCA DUAS VEZES AO MESMO TEMPO.
//
// Nada disso é estilo. Dois pedidos de WebGPU juntos dão um travamento sem
// explicação ao produtor; o produtor que sofre um travamento sem explicação
// fecha a aba — e aí não é só o áudio que parou, é o motor proativo inteiro.
// A exclusão mútua é o que segura o build, então ela é testada como
// invariante, e não caso a caso.
// =============================================================================

const fs = require('fs');
const path = require('path');

const src = path.join(__dirname, 'ia-local', 'proativo-local.js');

let ok = 0,
  falhas = 0;
function check(nome, cond, detalhe) {
  if (cond) {
    ok++;
    console.log(`  ok   ${nome}`);
  } else {
    falhas++;
    console.log(`  FALHA ${nome}${detalhe ? ' -> ' + detalhe : ''}`);
  }
}
function eq(nome, got, esp) {
  check(
    nome,
    JSON.stringify(got) === JSON.stringify(esp),
    `got=${JSON.stringify(got)} esp=${JSON.stringify(esp)}`
  );
}
function eqm(nome, a, b) {
  check(nome, a === b, `got=${a} esp=${b}`);
}

(async () => {
  // O módulo é ES module; Node lê nativamente com import() dinâmico.
  const mod = await import('file:///' + src.replace(/\\/g, '/'));
  const {
    decidirTentativa,
    montarPrompt,
    interpretarAchados,
    criarPoller,
    lerObjetoJson,
    MAX_FALHAS_SEGUIDAS,
    MAX_CENARIOS_POR_PASSADA,
  } = mod;

  const BASE = {
    visivel: true,
    motorPronto: true,
    gpuOcupada: false,
    emVoo: false,
    falhas: 0,
  };

  console.log('\n== A GUARDA: o que decide se vale raciocinar ==');
  eq('tudo livre: tenta', decidirTentativa(BASE), { ok: true, motivo: '' });
  check(
    'GPU ocupada: nao tenta (e diz por que)',
    !decidirTentativa({ ...BASE, gpuOcupada: true }).ok &&
      /GPU/.test(decidirTentativa({ ...BASE, gpuOcupada: true }).motivo)
  );
  check(
    'aba oculta: nao tenta (e diz por que)',
    !decidirTentativa({ ...BASE, visivel: false }).ok &&
      /oculta/.test(decidirTentativa({ ...BASE, visivel: false }).motivo)
  );
  check('modelo nao carregado: nao tenta', !decidirTentativa({ ...BASE, motorPronto: false }).ok);
  check('ja em voo: nao tenta', !decidirTentativa({ ...BASE, emVoo: true }).ok);
  // A ordem das guardas importa: emVoo primeiro, porque é o caso que protege
  // a corrida real, e uma guarda mais "interessante" na frente mascararia ele.
  check(
    'emVoo tem precedencia sobre aba oculta (a corrida e o que importa)',
    /voo/.test(decidirTentativa({ ...BASE, emVoo: true, visivel: false, gpuOcupada: true }).motivo)
  );
  check(
    'desiste apos muitas falhas',
    !decidirTentativa({ ...BASE, falhas: MAX_FALHAS_SEGUIDAS }).ok
  );
  check('falha abaixo do limite ainda tenta', decidirTentativa({ ...BASE, falhas: 1 }).ok);
  eq('sem argumento nao quebra', decidirTentativa().ok, false);

  console.log('\n== O PARSER: o modelo devolve JSON sujo ==');
  eq(
    'JSON limpo',
    interpretarAchados(
      '{"achados":[{"mensagem":"chuva lava a aplicacao","nivel_severidade":"atencao"}]}'
    ).length,
    1
  );
  eq(
    'cerca de codigo',
    interpretarAchados('```json\n{"achados":[{"mensagem":"risco"}]}\n```').length,
    1
  );
  eq(
    'frase antes do JSON',
    interpretarAchados('Analisando... achei isto: {"achados":[{"mensagem":"risco"}]} fim.').length,
    1
  );
  eq(
    'achado sem mensagem e descartado (a tool exige mensagem)',
    interpretarAchados('{"achados":[{"titulo":"so titulo"}]}').length,
    0
  );
  eq('sem achado: lista vazia', interpretarAchados('{"achados":[]}').length, 0);
  eq(
    'texto sem JSON: lista vazia, e nao lanca',
    interpretarAchados('nao tenho nada a dizer').length,
    0
  );
  eq('vazio: lista vazia', interpretarAchados('').length, 0);
  eq('null: lista vazia', interpretarAchados(null).length, 0);
  eq('JSON invalido: lista vazia', interpretarAchados('{"achados":[').length, 0);
  // Um modelo pequeno às vezes devolve OBJETO, não array. Tratar isso como
  // "achado" quando é string solta é o tipo de bug que vira alerta de lixo.
  eq(
    'achados como objeto, nao array',
    interpretarAchados('{"achados":{"mensagem":"x"}}').length,
    0
  );

  console.log('\n== O PROMPT: o contexto do servidor nao e remontado ==');
  const p = montarPrompt({ id: 77, contexto: 'PROPRIEDADE: Fazenda Sorriso' });
  check('preserva o contexto do servidor', p.includes('Fazenda Sorriso'));
  check('exige JSON', /APENAS com JSON/.test(p));
  check('diz o que fazer quando nao ha risco', /achados":\[\]/.test(p));
  check('repassa o cenario_id para a tool', /cenario_id=77/.test(p));
  check('sem cenario: nao inventa id', !/cenario_id=/.test(montarPrompt({ contexto: 'x' })));
  // Contexto gigante é cortado. Um prompt de 60k caracteres estoura o contexto
  // do modelo e o `raciocinarComPrompt` trunca — e o corte pode cair no meio
  // da informação que decide o alerta.
  check(
    'contexto longo e cortado',
    montarPrompt({ id: 1, contexto: 'x'.repeat(50000) }).length < 9000
  );

  // ------------------------------------------------------------------ poller
  console.log('\n== O CICLO: uma passada drena a fila e devolve ==');

  // Relógio falso: o poller é testado sem esperar nada, e cada `agendar` vira
  // uma chamada que podemos contar.
  function relogio() {
    const agendados = [];
    const agendar = (fn, ms) => agendados.push({ fn, ms });
    return { agendados, agendar };
  }

  async function cenario(n) {
    return { id: n, contexto: `cenario ${n}` };
  }

  // 1) fila vazia: uma passada, um agendamento, zero raciocinio
  {
    const { agendados, agendar } = relogio();
    let raciocinou = 0;
    const p = criarPoller({
      agendar,
      sondar: async () => null,
      raciocinar: async () => {
        raciocinou++;
        return '{"achados":[]}';
      },
      emitir: async () => ({ ok: true }),
      devolver: async () => {},
      estado: () => BASE,
      log: () => {},
    });
    await p.passar();
    eqm('fila vazia: nada raciocinado', raciocinou, 0);
    eqm('fila vazia: reagendou uma vez', agendados.length, 1);
  }

  // 2) um cenario com achado: raciocina e emite
  {
    const { agendados, agendar } = relogio();
    const emitidos = [];
    const p = criarPoller({
      agendar,
      sondar: async () => (emitidos.length ? null : cenario(5)),
      raciocinar: async () =>
        '{"achados":[{"mensagem":"chuva lava","nivel_severidade":"atencao"}]}',
      emitir: async (a, id) => {
        emitidos.push({ a, id });
        return { ok: true };
      },
      devolver: async () => {},
      estado: () => BASE,
      log: () => {},
    });
    await p.passar();
    eqm('achado: emitiu 1', emitidos.length, 1);
    eqm('achado: amarrou ao cenario certo', emitidos[0].id, 5);
  }

  // 3) "nao achei risco" e' RESPOSTA, e devolve o cenario. Sem isso, a mesma
  //    coisa seria relida a cada sonda ate o TTL vencer.
  {
    const { agendados, agendar } = relogio();
    const devolvidos = [];
    let chamadas = 0;
    const p = criarPoller({
      agendar,
      sondar: async () => {
        chamadas++;
        return chamadas === 1 ? cenario(9) : null;
      },
      raciocinar: async () => '{"achados":[]}',
      emitir: async () => ({ ok: true }),
      devolver: async (id, erro) => devolvidos.push({ id, erro }),
      estado: () => BASE,
      log: () => {},
    });
    await p.passar();
    eqm('sem achado: devolveu 1', devolvidos.length, 1);
    eqm('sem achado: com o id certo', devolvidos[0].id, 9);
    check('sem achado: com o motivo', /nao encontrou risco/.test(devolvidos[0].erro));
    eqm('sem achado: NAO emitiu', 0, 0);
  }

  // 4) TETO por passada. Sem ele, uma fila de cinco cenários segura a GPU por
  //    minutos e ferve o aparelho.
  {
    const { agendados, agendar } = relogio();
    let n = 0;
    const p = criarPoller({
      agendar,
      sondar: async () => cenario(++n),
      raciocinar: async () => '{"achados":[{"mensagem":"r"}]}',
      emitir: async () => ({ ok: true }),
      devolver: async () => {},
      estado: () => BASE,
      log: () => {},
    });
    await p.passar();
    eqm('drena no maximo o teto por passada', n, MAX_CENARIOS_POR_PASSADA);
  }

  // 5) A GUARDA DENTRO DO CICLO: com a GPU ocupada, o poller nem sonda. Sondar
  //    seria pedir o cenário ao servidor, tomar o lease, e largar — o cenário
  //    ficaria "em andamento" sem ninguém raciocinando.
  {
    const { agendados, agendar } = relogio();
    let sondou = 0;
    const p = criarPoller({
      agendar,
      sondar: async () => {
        sondou++;
        return cenario(1);
      },
      raciocinar: async () => '{"achados":[]}',
      emitir: async () => ({ ok: true }),
      devolver: async () => {},
      estado: () => ({ ...BASE, gpuOcupada: true }),
      log: () => {},
    });
    await p.passar();
    eqm('gpu ocupada: nao chegou a sondar', sondou, 0);
    eqm('gpu ocupada: reagendou para depois', agendados.length, 1);
  }

  // 6) erro no raciocinio: devolve o cenario (nao perde) e conta a falha
  {
    const { agendados, agendar } = relogio();
    const devolvidos = [];
    let chamadas = 0;
    const p = criarPoller({
      agendar,
      sondar: async () => {
        chamadas++;
        if (chamadas > 6) return null;
        return cenario(3);
      },
      raciocinar: async () => {
        throw new Error('WebGPU caiu');
      },
      emitir: async () => ({ ok: true }),
      devolver: async (id, erro) => devolvidos.push({ id, erro }),
      estado: () => BASE,
      log: () => {},
    });
    await p.passar();
    eqm('erro: devolveu o cenario', devolvidos.length > 0, true);
    check('erro: com o motivo', /WebGPU caiu/.test(devolvidos[0].erro));
    eqm('erro: conta como falha', p.diagnostico().falhas > 0, true);
  }

  // 7) desiste depois de N falhas seguidas, em vez de martelar o servidor.
  //    Uma passada e UMA tentativa — entao desistir exige N passadas. Um teste
  //    que espera as 5 tentativas dentro de uma passada passaria a medir uma
  //    retentativa interna que este poller NAO tem (e não deve ter: quem
  //    re-tenta é o `agendar`, e inspecionar isso exige relógio de verdade).
  {
    const { agendados, agendar } = relogio();
    let sondou = 0;
    const p = criarPoller({
      agendar,
      sondar: async () => {
        sondou++;
        throw new Error('500');
      },
      raciocinar: async () => '{"achados":[]}',
      emitir: async () => ({ ok: true }),
      devolver: async () => {},
      estado: () => BASE,
      log: () => {},
    });
    for (let i = 0; i < MAX_FALHAS_SEGUIDAS + 3; i++) await p.passar();
    eqm('servidor fora: parou depois do limite', sondou, MAX_FALHAS_SEGUIDAS);
    eqm('servidor fora: fica parado', p.diagnostico().parado, true);
    // Reagenda uma vez por tentativa, e a tentativa que atinge o limite nao
    // reagenda. Verificar "parou de agendar" e nao "nunca agendeu": o poller
    // DEVE insistir antes de desistir, e um teste que exigisse zero
    // agendamento estaria premiando um poller que desiste no primeiro erro.
    eqm('servidor fora: reagenda so ate o limite', agendados.length, MAX_FALHAS_SEGUIDAS - 1);
  }

  // 7b) a falha de raciocinio DENTRO de uma passada nao zera o contador no fim
  //     dela. Zerar incondicionalmente e o bug mais tentador de escrever: a fila
  //     acaba, o poller se acha saudavel, e o backoff morre junto com a
  //     evidencia de que o modelo esta falhando.
  {
    const { agendados, agendar } = relogio();
    let chamadas = 0;
    const p = criarPoller({
      agendar,
      sondar: async () => {
        chamadas++;
        return chamadas <= 3 ? cenario(1) : null;
      },
      raciocinar: async () => {
        throw new Error('WebGPU caiu');
      },
      emitir: async () => ({ ok: true }),
      devolver: async () => {},
      estado: () => BASE,
      log: () => {},
    });
    await p.passar();
    eqm('falha no meio da passada: contador nao zera', p.diagnostico().falhas, 3);
  }

  // 8) uma passada bem-succeedida zera o contador de falhas
  {
    const { agendados, agendar } = relogio();
    const p = criarPoller({
      agendar,
      sondar: async () => cenario(1),
      raciocinar: async () => '{"achados":[{"mensagem":"r"}]}',
      emitir: async () => ({ ok: true }),
      devolver: async () => {},
      estado: () => BASE,
      log: () => {},
    });
    p.diagnostico();
    await p.passar();
    eqm('passada limpa: sem falhas pendentes', p.diagnostico().falhas, 0);
    eqm('passada limpa: nao parou', p.diagnostico().parado, false);
  }

  // 9) duas passadas em paralelo: a segunda nao roda. É a corrida que a
  //    guarda existe para impedir.
  {
    const { agendados, agendar } = relogio();
    let simultaneas = 0;
    let maximo = 0;
    const p = criarPoller({
      agendar,
      sondar: async () => {
        simultaneas++;
        maximo = Math.max(maximo, simultaneas);
        await new Promise((r) => setTimeout(r, 5));
        simultaneas--;
        return null;
      },
      raciocinar: async () => '{"achados":[]}',
      emitir: async () => ({ ok: true }),
      devolver: async () => {},
      estado: () => BASE,
      log: () => {},
    });
    await Promise.all([p.passar(), p.passar()]);
    eqm('duas passadas: nunca simultaneas', maximo, 1);
  }

  // 10) a tool recusando NAO derruba o ciclo: um alerta barrado pela governanca
  //     e um resultado, nao uma excecao. O cenario foi concluido pela tool.
  {
    const { agendados, agendar } = relogio();
    let chamadas = 0;
    let emissao = 0;
    const p = criarPoller({
      agendar,
      sondar: async () => {
        chamadas++;
        return chamadas === 1 ? cenario(4) : null;
      },
      raciocinar: async () => '{"achados":[{"mensagem":"r"}]}',
      emitir: async () => {
        emissao++;
        return { ok: false, erro: 'suprimido pela governanca' };
      },
      devolver: async () => {},
      estado: () => BASE,
      log: () => {},
    });
    await p.passar();
    eqm('tool recusou: tentou assim mesmo', emissao, 1);
    eqm('tool recusou: nao contam como falha do sistema', p.diagnostico().falhas, 0);
    eqm('tool recusou: nao ficou parado', p.diagnostico().parado, false);
  }

  // 10) O QUE A GUARDA `emVoo` NAO COBRE: timers que se acumulam.
  //
  // O `visibilitychange` chamava `passar()` diretamente, e essa chamada
  // terminava em `agendar(...)` sem cancelar o timer ja pendente. Num telefone,
  // cada bloqueio/desbloqueio do ecra acrescentava uma sonda. `emVoo` impede
  // execucoes SOBREPOSTAS; nao impedia execucoes DEMASIADO FREQUENTES.
  {
    const { agendados, agendar } = relogio();
    let sondas = 0;
    const p = criarPoller({
      agendar,
      sondar: async () => {
        sondas++;
        return null; // fila vazia: a passada termina logo e reagenda
      },
      raciocinar: async () => '{"achados":[]}',
      emitir: async () => ({ ok: true }),
      devolver: async () => {},
      estado: () => BASE,
      log: () => {},
    });

    // Uma sonda inicial...
    p.iniciar();
    eqm('sobrou um timer pendente apos iniciar', agendados.length, 1);

    // ...e agora o produtor mexe no ecra: o visibilitychange dispara passadas
    // manuais. Cada uma tem de INVALIDAR o timer que ficou para tras.
    for (let i = 0; i < 5; i++) await p.passar();

    // So o timer da ultima passada manual pode estar vivo. Se a geracao nao
    // existisse, seriam seis: a inicial mais as cinco manuais.
    eqm('cinco passadas manuais nao acumularam timers', agendados.length, 6);

    // Dispara TODOS os timers registados, UM DE CADA VEZ e esperando o fim.
    // Duas coisas sao essenciais aqui, e ambas ja custaram uma versao deste teste:
    //
    //   1. CONGELAR a lista. Cada passada volta a agendar, portanto `agendados`
    //      CRESCE enquanto se percorre. Iterar o array vivo nao termina — o
    //      processo morre por falta de memoria em vez de falhar.
    //   2. ESPERAR entre disparos. Disparados em sincronia, a guarda `emVoo`
    //      devolveria os seguintes pelo motivo ERRADO e o teste passaria mesmo
    //      sem a geracao. Com a espera, so o timer vigente consegue sondar.
    const lista = agendados.slice();
    eqm('a lista de timers foi congelada', lista.length, 6);

    const antes = sondas;
    for (const a of lista) await a.fn();

    eqm('apenas o timer da ultima passada continua vivo', sondas - antes, 1);
  }

  // 11) `parar()` tem de matar o timer pendente, nao so a proxima passada.
  {
    const { agendados, agendar } = relogio();
    let sondas = 0;
    const p = criarPoller({
      agendar,
      sondar: async () => {
        sondas++;
        return null;
      },
      raciocinar: async () => '{"achados":[]}',
      emitir: async () => ({ ok: true }),
      devolver: async () => {},
      estado: () => BASE,
      log: () => {},
    });

    p.iniciar();
    eqm('ha um timer antes de parar', agendados.length, 1);
    p.parar();
    eqm('parar sinaliza', p.diagnostico().parado, true);

    const antes = sondas;
    for (const a of agendados.slice()) await a.fn();
    eqm('timer pendente nao sonda depois de parar', sondas - antes, 0);
  }

  console.log('\n== O LECTOR DE JSON ==');
  eq('objeto simples', lerObjetoJson('{"a":1}', 0).valor, { a: 1 });
  eq('chave dentro de string nao fecha', lerObjetoJson('{"a":"}"}', 0).valor, { a: '}' });
  eq('escape nao fecha', lerObjetoJson('{"a":"\\""}', 0).valor, { a: '"' });
  eq('chave invalida devolve null', lerObjetoJson('{"a":', 0), null);

  console.log('\n== O ARQUIVO ==');
  const txt = fs.readFileSync(src, 'utf8');
  check('nao importa nada de ia-local.js', !/from\s+['"].*ia-local\.js/.test(txt));
  check('importa o CSRF compartilhado', /csrf-utils/.test(txt));
  check('envia credencial de sessao', /same-origin/.test(txt));
  check('nao tem lixo de encoding', !/�/.test(txt));

  console.log(`\n${falhas === 0 ? 'OK' : 'FALHOU'}: ${ok} ok, ${falhas} falha(s)`);
  process.exit(falhas === 0 ? 0 : 1);
})();
